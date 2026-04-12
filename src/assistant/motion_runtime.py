"""辅车底座主数据链运行时.

@file src/assistant/motion_runtime.py
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)


def _debug_print(stage, **payload):
    if not payload:
        print("[assistant.motion] %s" % str(stage))
        return
    parts = []
    for key in sorted(payload):
        parts.append("%s=%s" % (str(key), str(payload[key])))
    print("[assistant.motion] %s | %s" % (str(stage), ", ".join(parts)))


if _USE_DIRECT_IMPORTS:
    import config
    import runtime_params
    from ctrl.attitude import (
        HeadingEstimator,
        capture_heading_target,
        compute_heading_correction,
        update_heading_from_gyro,
    )
    from ctrl.filters import LowPassFilter, build_wheel_filter_bank, update_wheel_speeds
    from ctrl.filters import set_wheel_filter_dt_s
    from ctrl.kinematics import (
        build_kinematics,
        build_odometry,
        resolve_follow_velocity,
        rotate_body_delta_to_world,
        scale_wheel_targets,
        update_odometry_from_wheels,
    )
    from ctrl.pid import (
        apply_wheel_speed_control,
        build_wheel_speed_controllers,
        reset_wheel_speed_control,
    )
    from safety import SafetyGuard
    from state import MotionRuntimeState
    from status import render_state
else:
    from . import config, runtime_params
    from .ctrl.attitude import (
        HeadingEstimator,
        capture_heading_target,
        compute_heading_correction,
        update_heading_from_gyro,
    )
    from .ctrl.filters import (
        LowPassFilter,
        build_wheel_filter_bank,
        set_wheel_filter_dt_s,
        update_wheel_speeds,
    )
    from .ctrl.kinematics import (
        build_kinematics,
        build_odometry,
        resolve_follow_velocity,
        rotate_body_delta_to_world,
        scale_wheel_targets,
        update_odometry_from_wheels,
    )
    from .ctrl.pid import (
        apply_wheel_speed_control,
        build_wheel_speed_controllers,
        reset_wheel_speed_control,
    )
    from .safety import SafetyGuard
    from .state import MotionRuntimeState
    from .status import render_state


def _clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


_TRANSLATION_IDLE = "idle"
_TRANSLATION_FOLLOW = "follow"
_TRANSLATION_VELOCITY = "velocity"
_TURN_AUTO = "auto"
_TURN_MANUAL = "manual"


def _load_ident_lookup(path):
    """读取轮速辨识参数表

    @brief 启动时把文本辨识结果转成按轮名索引的查询表。
    @param path 辨识结果文件路径
    @return dict
    """

    lookup = {}
    try:
        with open(path, "r") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    lookup[str(parts[0])] = (float(parts[1]), float(parts[2]))
                except ValueError:
                    continue
    except OSError:
        return {}
    return lookup


def _load_gyro_offsets(path):
    """读取陀螺仪零漂参数

    @brief 兼容六轴完整格式和旧版单值格式, 启动时统一收口为六元组。
    @param path 零漂文件路径
    @return tuple
    """

    offsets = [0.0] * 6
    try:
        with open(path, "r") as handle:
            content = handle.read().strip()
    except OSError:
        return tuple(offsets)
    if not content:
        return tuple(offsets)
    parts = content.split(",")
    try:
        if len(parts) == 6:
            for index in range(6):
                offsets[index] = float(parts[index])
        else:
            offsets[5] = float(content)
    except ValueError:
        return tuple([0.0] * 6)
    return tuple(offsets)


def _trace_ident_lookup_loaded(path, ident_lookup):
    wheel_ident = {}
    for name in ("m", "l", "r"):
        if name not in ident_lookup:
            continue
        wheel_ident[name] = ident_lookup[name]
    _debug_print(
        "ident_lookup_loaded",
        path=path,
        wheel_ident=wheel_ident,
    )


def _trace_gyro_offsets_loaded(path, gyro_offsets):
    _debug_print(
        "gyro_offsets_loaded",
        path=path,
        gyro_offsets=tuple(gyro_offsets),
    )


def _bind_runtime_hw_bundle(runtime_state, hw_bundle):
    if hw_bundle is None:
        return runtime_state
    if runtime_state.hw_bundle is not None and runtime_state.hw_bundle is not hw_bundle:
        raise ValueError("runtime_state 与 hw_bundle 必须引用同一套装配")
    runtime_state.hw_bundle = hw_bundle
    return runtime_state


def _state_line(state):
    # 状态回包统一交给独立序列化入口, 运行时只负责提供当前状态对象
    return render_state(state)


def _bind_state_line(state):
    # 运行时装配实例方法, 避免把状态模块重新耦回序列化层。
    state.state_line = lambda: _state_line(state)


def _motor_bundle(state):
    if state.hw_bundle is None:
        return None
    return state.hw_bundle.get("motors")


def _imu_bundle(state):
    if state.hw_bundle is None:
        return None
    return state.hw_bundle.get("imu")


def _encoder_bundle(state):
    if state.hw_bundle is None:
        return None
    return state.hw_bundle.get("encoders")


def _mark_control_applied(state, cycle_token=None):
    state._last_control_cycle_token = cycle_token


def _control_already_applied(state, cycle_token=None):
    return cycle_token is not None and cycle_token == state._last_control_cycle_token


def _heading_chain_ready(state):
    imu = _imu_bundle(state)
    if imu is None:
        return False
    return any(
        getattr(imu, name, None) is not None
        for name in ("read_calibrated", "heading_deg", "read_raw")
    )


def _encoder_chain_ready(state):
    """检查编码器链路是否可用

    @brief 只有三路编码器对象都具备读取能力时, 才允许底座链路标记为可用。
    @param state 当前辅车运行时状态
    @return bool
    """

    encoders = _encoder_bundle(state)
    if encoders is None:
        return False
    for name in ("m", "l", "r"):
        port = encoders.get(name)
        if port is None:
            return False
        if (
            getattr(port, "read_and_clear", None) is None
            and getattr(port, "read", None) is None
        ):
            return False
    return True


def _update_base_ok(state):
    state.base_ok = _heading_chain_ready(state) and _encoder_chain_ready(state)


def _clear_follow_target(state):
    state.follow_target_world = None


def _capture_follow_target(state, dx, dy):
    offset_x, offset_y = rotate_body_delta_to_world(dx, dy, state.heading_deg)
    if state.follow_target_world is None:
        base_x = float(state.odom[0])
        base_y = float(state.odom[1])
    else:
        base_x = float(state.follow_target_world[0])
        base_y = float(state.follow_target_world[1])
    state.follow_target_world = (
        base_x + float(offset_x),
        base_y + float(offset_y),
    )


def _clear_velocity_target(state):
    state.follow_velocity_target = (0.0, 0.0)


def _set_translation_mode(state, mode):
    state.translation_mode = str(mode)
    state.follow_active = mode != _TRANSLATION_IDLE


def _set_velocity_target(state, vx, vy):
    state.follow_velocity_target = (float(vx), float(vy))


def _set_turn_auto(state, capture_current_heading=False):
    if capture_current_heading:
        capture_heading_target(state)
    state.turn_source = _TURN_AUTO
    state.manual_omega_target = 0.0


def _set_turn_manual(state, omega):
    capture_heading_target(state)
    state.turn_source = _TURN_MANUAL
    state.manual_omega_target = _clamp(
        float(omega), -float(state.auto_omega_max), float(state.auto_omega_max)
    )


def _clear_mode_state(state, capture_current_heading=False):
    _set_translation_mode(state, _TRANSLATION_IDLE)
    _set_turn_auto(state, capture_current_heading=capture_current_heading)
    _clear_follow_target(state)
    _clear_velocity_target(state)


def _resolve_translation_command(state):
    if state.translation_mode == _TRANSLATION_FOLLOW:
        return resolve_follow_velocity(state)
    if state.translation_mode == _TRANSLATION_VELOCITY:
        return (
            float(state.follow_velocity_target[0]),
            float(state.follow_velocity_target[1]),
        )
    return (0.0, 0.0)


def _resolve_turn_command(state):
    if state.turn_source == _TURN_MANUAL:
        return float(state.manual_omega_target)
    return compute_heading_correction(state)


def _read_imu_sample(state):
    """读取一帧姿态输入

    @brief 统一兼容校准输出、直接航向角和原始陀螺仪三种 IMU 接口形态。
    @param state 当前辅车运行时状态
    @return float | None
    """

    imu = _imu_bundle(state)
    heading_override = None
    if imu is None:
        state.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        state.imu_calibrated = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return heading_override

    read_calibrated = getattr(imu, "read_calibrated", None)
    if read_calibrated is not None:
        state.imu_calibrated = tuple(read_calibrated())
        state.imu_raw = tuple(getattr(imu, "last_raw", state.imu_calibrated))
        return heading_override
    if hasattr(imu, "heading_deg"):
        heading_override = float(imu.heading_deg())
        state.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        state.imu_calibrated = state.imu_raw
        return heading_override
    read_raw = getattr(imu, "read_raw", None)
    if read_raw is None:
        state.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        state.imu_calibrated = state.imu_raw
        return heading_override
    state.imu_raw = tuple(read_raw())
    calibrated = []
    for index, value in enumerate(state.imu_raw):
        calibrated.append(float(value) - float(state.imu_offsets[index]))
    state.imu_calibrated = tuple(calibrated)
    return heading_override


def _read_encoder_ticks(state):
    """读取一轮编码器脉冲

    @brief 优先消费可清空计数的接口, 保证速度估计使用本周期增量。
    @param state 当前辅车运行时状态
    @return dict
    """

    encoders = _encoder_bundle(state)
    if encoders is None:
        return {"m": 0.0, "l": 0.0, "r": 0.0}

    raw_ticks = {}
    for name in ("m", "l", "r"):
        port = encoders.get(name)
        if port is None:
            raw_ticks[name] = 0.0
            continue
        reader = getattr(port, "read_and_clear", None)
        if reader is not None:
            raw_ticks[name] = float(reader())
            continue
        read_ticks = getattr(port, "read", None)
        if read_ticks is None:
            raw_ticks[name] = 0.0
            continue
        raw_ticks[name] = float(read_ticks())
        clearer = getattr(port, "clear", None)
        if clearer is not None:
            clearer()
    return raw_ticks


def _refresh_base_chain(state, cycle_token=None):
    """刷新底座基础观测链

    @brief 在单个周期内复用姿态、编码器和里程计快照。
    @param state 当前辅车运行时状态
    @param cycle_token 当前周期令牌
    @return dict
    """

    if cycle_token is not None and cycle_token == state._last_cycle_token:
        if state._last_base_snapshot is None:
            return {}
        return dict(state._last_base_snapshot)

    # 先刷新链路可用性和原始传感器输入
    _update_base_ok(state)

    odom_heading_deg = float(state.heading_deg)
    heading_override = _read_imu_sample(state)
    update_heading_from_gyro(state, heading_override=heading_override)
    has_valid_attitude_dt = float(state.tick_s) > 0.0

    # 再根据周期时长决定是否推进滤波和里程计
    raw_ticks = _read_encoder_ticks(state)
    state.encoder_ticks = dict(raw_ticks)
    if has_valid_attitude_dt:
        set_wheel_filter_dt_s(state.wheel_filters, ("m", "l", "r"), state.tick_s)
        state.wheel_speeds = update_wheel_speeds(
            state.wheel_filters,
            raw_ticks,
            ("m", "l", "r"),
        )
        odom_x, odom_y = update_odometry_from_wheels(
            state, heading_deg=odom_heading_deg
        )
    else:
        set_wheel_filter_dt_s(state.wheel_filters, ("m", "l", "r"), 0.0)
        update_wheel_speeds(state.wheel_filters, raw_ticks, ())
        state.wheel_speeds = dict(state.wheel_speeds)
        odom_x = float(state.odom[0])
        odom_y = float(state.odom[1])
    # 最后缓存本轮快照, 供同周期的命令处理和 tick 复用
    snapshot = {
        "imu_raw": tuple(state.imu_raw),
        "encoder_ticks": dict(state.encoder_ticks),
        "heading_est_deg": float(state.heading_deg),
        "odom": (float(state.odom[0]), float(state.odom[1])),
        "yaw_rate_deg_s": float(state.yaw_rate_deg_s),
        "base_ok": 1 if state.base_ok else 0,
    }
    state._last_cycle_token = cycle_token
    state._last_base_snapshot = dict(snapshot)
    return snapshot


def _apply_motor_output(state, dx, dy, omega):
    """把车体速度指令落到三轮输出

    @brief 更新目标轮速并把结果写到三轮输出。
    @param state 当前辅车运行时状态
    @param dx 车体 x 方向速度命令
    @param dy 车体 y 方向速度命令
    @param omega 角速度命令
    @return dict | None
    """

    wheel_targets = state.kinematics.inverse_kinematics(
        float(dx), float(dy), float(omega)
    )
    wheel_targets = scale_wheel_targets(
        wheel_targets,
        runtime_params.FOLLOW_OUTPUT_LIMIT,
    )
    motors = _motor_bundle(state)
    apply_wheel_speed_control(
        state,
        wheel_targets,
        limit=runtime_params.FOLLOW_OUTPUT_LIMIT,
        motors=motors,
    )


def _reset_speed_loop(state):
    reset_wheel_speed_control(state)


def _stop_motors(state):
    _reset_speed_loop(state)
    motors = _motor_bundle(state)
    if motors is None:
        return
    for motor in motors.values():
        stop = getattr(motor, "stop", None)
        if stop is not None:
            stop()
        else:
            motor.set_duty(0)


def _stop(state, reason="", cycle_token=None):
    _refresh_base_chain(state, cycle_token=cycle_token)
    state.state_label = "TIMEOUT" if reason == "timeout_stop" else "IDLE"
    state.velocity_command = (0.0, 0.0, 0.0)
    state.timeout = reason == "timeout_stop"
    state.last_error = str(reason)
    _clear_mode_state(state, capture_current_heading=True)
    _stop_motors(state)
    _mark_control_applied(state, cycle_token=cycle_token)


def _hold_heading_in_timeout(state, cycle_token=None):
    _refresh_base_chain(state, cycle_token=cycle_token)
    state.state_label = "TIMEOUT"
    state.timeout = True
    _set_translation_mode(state, _TRANSLATION_IDLE)
    _clear_follow_target(state)
    _clear_velocity_target(state)
    _set_turn_auto(state, capture_current_heading=False)
    omega = _resolve_turn_command(state)
    state.velocity_command = (0.0, 0.0, omega)
    _apply_motor_output(state, 0.0, 0.0, omega)
    _mark_control_applied(state, cycle_token=cycle_token)
    state.last_error = "timeout_stop"


def _preserve_timeout_stop(state, cycle_token=None):
    _refresh_base_chain(state, cycle_token=cycle_token)
    state.velocity_command = (0.0, 0.0, 0.0)
    state.state_label = "TIMEOUT"
    state.timeout = True
    _clear_mode_state(state, capture_current_heading=True)
    _stop_motors(state)
    _mark_control_applied(state, cycle_token=cycle_token)
    state.last_error = "timeout_stop"


def _is_timeout_locked(state):
    return bool(state.timeout) or state.state_label == "TIMEOUT"


def _clear_follow_deadline(state):
    state.safety.last_command_ms = None


def _reject_unsupported_command(state, cycle_token=None):
    _refresh_base_chain(state, cycle_token=cycle_token)
    if not _is_timeout_locked(state):
        state.timeout = False
    state.last_error = "unsupported_command"
    return "ERR"


def _apply_follow(state, command, now_ms, cycle_token=None):
    """执行一条跟随报文

    @brief 根据相对位移目标刷新跟随状态并推进一次控制输出。
    @param state 当前辅车运行时状态
    @param command 已解析跟随命令
    @param now_ms 当前毫秒时间
    @param cycle_token 当前周期令牌
    @return str
    """

    _refresh_base_chain(state, cycle_token=cycle_token)
    if int(command.seq) <= int(state.last_seq):
        return "IGNORED"
    state.safety.mark_command(now_ms)
    state.safety.clear_estop()
    state.last_error = ""
    state.timeout = False
    state.last_seq = int(command.seq)
    if not command.valid:
        state.state_label = "IDLE"
        state.velocity_command = (0.0, 0.0, 0.0)
        _clear_mode_state(state, capture_current_heading=True)
        _stop_motors(state)
        _mark_control_applied(state, cycle_token=cycle_token)
        return "HOLD"
    _set_translation_mode(state, _TRANSLATION_FOLLOW)
    state.state_label = "BUSY"
    target_dx = _clamp(
        float(command.dx),
        -float(runtime_params.FOLLOW_OUTPUT_LIMIT),
        float(runtime_params.FOLLOW_OUTPUT_LIMIT),
    )
    target_dy = _clamp(
        float(command.dy),
        -float(runtime_params.FOLLOW_OUTPUT_LIMIT),
        float(runtime_params.FOLLOW_OUTPUT_LIMIT),
    )
    _capture_follow_target(state, target_dx, target_dy)
    _clear_velocity_target(state)
    _set_turn_auto(state, capture_current_heading=state.turn_source == _TURN_MANUAL)
    control_dx, control_dy = _resolve_translation_command(state)
    omega = _resolve_turn_command(state)
    state.velocity_command = (control_dx, control_dy, omega)
    _apply_motor_output(state, control_dx, control_dy, omega)
    _mark_control_applied(state, cycle_token=cycle_token)
    return "BUSY"


def _apply_velocity(state, command, now_ms, cycle_token=None):
    """执行一条直接速度命令

    @brief 按直接速度命令推进安全、航向保持和轮速控制链路。
    @param state 当前辅车运行时状态
    @param command 已解析速度命令
    @param now_ms 当前毫秒时间
    @param cycle_token 当前周期令牌
    @return str
    """

    _refresh_base_chain(state, cycle_token=cycle_token)
    state.safety.mark_command(now_ms)
    state.safety.clear_estop()
    state.last_error = ""
    state.timeout = False
    _set_translation_mode(state, _TRANSLATION_VELOCITY)
    state.state_label = "BUSY"
    _clear_follow_target(state)
    _set_velocity_target(state, command.vx, command.vy)
    released_manual_turn = state.turn_source == _TURN_MANUAL and abs(
        float(command.omega)
    ) < float(state.hold_speed_eps)
    if abs(float(command.omega)) >= float(state.hold_speed_eps):
        _set_turn_manual(state, command.omega)
    else:
        _set_turn_auto(state, capture_current_heading=released_manual_turn)
    control_dx, control_dy = _resolve_translation_command(state)
    limited_omega = _resolve_turn_command(state)
    state.velocity_command = (control_dx, control_dy, limited_omega)
    _apply_motor_output(
        state,
        state.velocity_command[0],
        state.velocity_command[1],
        state.velocity_command[2],
    )
    _mark_control_applied(state, cycle_token=cycle_token)
    return "BUSY"


def _apply_command(state, command, now_ms, cycle_token=None):
    """分发并执行辅车命令

    @brief 统一处理控制命令、运动命令和状态查询。
    @param state 当前辅车运行时状态
    @param command 已解析命令
    @param now_ms 当前毫秒时间
    @param cycle_token 当前周期令牌
    @return str
    """

    # 轻量查询命令直接返回
    if command.kind == "ping":
        return "ACK"
    if command.kind == "state_query":
        return state.state_line()

    # 运动相关命令统一经过专门分支
    if command.kind == "follow":
        return _apply_follow(state, command, now_ms, cycle_token=cycle_token)
    if command.kind == "follow_velocity":
        return _apply_velocity(state, command, now_ms, cycle_token=cycle_token)
    if command.kind == "arm":
        _refresh_base_chain(state, cycle_token=cycle_token)
        capture_heading_target(state)
        return "ACK"
    if command.kind == "disarm":
        _clear_follow_deadline(state)
        state.safety.trigger_estop()
        _stop(state, cycle_token=cycle_token)
        return "ACK"
    if command.kind == "stop":
        _clear_follow_deadline(state)
        state.safety.trigger_estop()
        _stop(state, "estop", cycle_token=cycle_token)
        return "DONE"
    if command.kind == "reset_odom":
        _clear_follow_deadline(state)
        state.odometry = build_odometry()
        state.odom[0] = 0.0
        state.odom[1] = 0.0
        state.heading_deg = 0.0
        state.target_heading_deg = 0.0
        state.yaw_rate_deg_s = 0.0
        state.last_yaw_rad = 0.0
        state.q_est = state.q_est.__class__()
        state.state_label = "IDLE"
        state.velocity_command = (0.0, 0.0, 0.0)
        state.timeout = False
        state.last_error = ""
        _clear_mode_state(state, capture_current_heading=True)
        _stop_motors(state)
        _mark_control_applied(state, cycle_token=cycle_token)
        state.safety.clear_estop()
        return "ACK"
    if command.kind == "hold":
        _clear_follow_deadline(state)
        should_refresh_heading_target = bool(state.follow_active) or not bool(
            state.heading_target_ready
        )
        if not _is_timeout_locked(state):
            state.state_label = "IDLE"
        state.velocity_command = (0.0, 0.0, 0.0)
        _clear_mode_state(state, capture_current_heading=should_refresh_heading_target)
        _stop_motors(state)
        _mark_control_applied(state, cycle_token=cycle_token)
        state.safety.clear_estop()
        return "DONE"
    # 未支持的命令最后统一走拒绝分支, 保持错误语义稳定
    if command.kind == "vel":
        return _apply_velocity(state, command, now_ms, cycle_token=cycle_token)
    if command.kind == "move":
        return _reject_unsupported_command(state, cycle_token=cycle_token)
    return _reject_unsupported_command(state, cycle_token=cycle_token)


def _tick(state, now_ms, cycle_token=None):
    """推进一轮辅车周期控制

    @brief 在每个控制周期里先做安全检查, 再决定继续跟随、保持姿态或停机。
    @param state 当前辅车运行时状态
    @param now_ms 当前毫秒时间
    @param cycle_token 当前周期令牌
    @return str
    """

    _refresh_base_chain(state, cycle_token=cycle_token)

    # 先处理急停和超时, 这些条件一旦触发就优先抢占后续控制输出
    if state.safety.should_stop(now_ms):
        if state.safety.estop_active:
            _stop(state, "estop", cycle_token=cycle_token)
        elif _is_timeout_locked(state):
            _hold_heading_in_timeout(state, cycle_token=cycle_token)
        else:
            _hold_heading_in_timeout(state, cycle_token=cycle_token)
        return "DONE"
    if _is_timeout_locked(state):
        if state.safety.estop_active:
            _preserve_timeout_stop(state, cycle_token=cycle_token)
        else:
            _hold_heading_in_timeout(state, cycle_token=cycle_token)
        return "DONE"
    if _control_already_applied(state, cycle_token=cycle_token):
        return "BUSY" if state.translation_mode != _TRANSLATION_IDLE else "ACK"

    # 再根据当前模式决定继续跟随目标还是退回姿态保持/空输出
    if state.translation_mode != _TRANSLATION_IDLE:
        dx, dy = _resolve_translation_command(state)
        omega = _resolve_turn_command(state)
        state.velocity_command = (dx, dy, omega)
        _apply_motor_output(state, dx, dy, omega)
        _mark_control_applied(state, cycle_token=cycle_token)
        return "BUSY"
    omega = _resolve_turn_command(state)
    state.velocity_command = (0.0, 0.0, omega)
    _apply_motor_output(state, 0.0, 0.0, omega)
    _mark_control_applied(state, cycle_token=cycle_token)
    return "ACK"


def create_runtime_state(timeout_ms=None, hw_bundle=None):
    """构造辅车运行时状态对象

    @brief 集中装配参数、控制器、传感器偏置和最小状态回包绑定。
    @param timeout_ms 命令超时阈值
    @param hw_bundle 可选硬件装配
    @return MotionRuntimeState
    """

    pid_map = dict(runtime_params.PID_MAP)
    ident_lookup = _load_ident_lookup(config.IDENT_RESULTS_FILE)
    imu_offsets = _load_gyro_offsets(config.GYRO_OFFSET_FILE)
    if timeout_ms is None:
        timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
    # 先写入运行时公共参数, 让后续控制链装配都从状态对象取统一配置
    state = MotionRuntimeState()
    state.hw_bundle = hw_bundle
    state.safety = SafetyGuard(timeout_ms=timeout_ms)
    state.pid_map = pid_map
    state.speed_filter_window = int(runtime_params.SPEED_FILTER_WINDOW)
    state.speed_diff_max_delta = float(runtime_params.SPEED_DIFF_MAX_DELTA)
    state.gyro_lpf_alpha = float(runtime_params.GYRO_LPF_ALPHA)
    state.yaw_kp = float(runtime_params.YAW_KP)
    state.yaw_ki = float(runtime_params.YAW_KI)
    state.yaw_kd = float(runtime_params.YAW_KD)
    state.yaw_i_max = float(runtime_params.YAW_I_MAX)
    state.auto_omega_max = float(runtime_params.AUTO_OMEGA_MAX)
    state.hold_speed_eps = float(runtime_params.HOLD_SPEED_EPS)
    state.heading_hold_enabled = True
    state.follow_position_kp = float(runtime_params.FOLLOW_POSITION_KP)
    state.follow_position_max_speed = float(runtime_params.FOLLOW_POSITION_MAX_SPEED)
    state.tick_ms = int(runtime_params.CONTROL_TICK_MS)
    state.tick_s = 0.0
    state.gyro_scale = float(config.GYRO_SCALE)
    state.ident_lookup = ident_lookup
    state.imu_offsets = (
        float(imu_offsets[0]),
        float(imu_offsets[1]),
        float(imu_offsets[2]),
        float(imu_offsets[3]),
        float(imu_offsets[4]),
        float(imu_offsets[5]),
    )
    # 再装配姿态、运动学、滤波器和轮速控制器, 收口底座主链依赖
    state.q_est = HeadingEstimator()
    state.kinematics = build_kinematics()
    state.odometry = build_odometry()
    state.gyro_lpf = LowPassFilter(runtime_params.GYRO_LPF_ALPHA, initial=0.0)
    state.wheel_filters = build_wheel_filter_bank(
        tick_ms=int(runtime_params.CONTROL_TICK_MS),
        wheel_names=("m", "l", "r"),
        window=runtime_params.SPEED_FILTER_WINDOW,
        max_delta=runtime_params.SPEED_DIFF_MAX_DELTA,
        long_window=runtime_params.LONG_WINDOW,
        short_window=runtime_params.SHORT_WINDOW,
    )
    state.wheel_controllers = build_wheel_speed_controllers(
        pid_map,
        ident_lookup,
        output_limit=runtime_params.MAX_DUTY,
    )
    # 最后绑定周期缓存和对外状态序列化入口, 便于命令与 tick 共享状态
    state._last_cycle_token = None
    state._last_base_snapshot = None
    state._last_control_cycle_token = None
    _bind_state_line(state)
    _trace_ident_lookup_loaded(config.IDENT_RESULTS_FILE, ident_lookup)
    _trace_gyro_offsets_loaded(config.GYRO_OFFSET_FILE, state.imu_offsets)
    imu = _imu_bundle(state)
    if imu is not None:
        apply_offsets = getattr(imu, "apply_offsets", None)
        if apply_offsets is not None:
            apply_offsets(state.imu_offsets)
    return state


def run_base_cycle(runtime_state, now_ms, cycle_token=None, hw_bundle=None):
    """执行一轮辅车周期推进

    @brief 对外暴露最小周期入口, 先绑定硬件 owner 再推进内部 tick。
    @param runtime_state 辅车运行时状态
    @param now_ms 当前毫秒时间
    @param cycle_token 当前周期令牌
    @param hw_bundle 可选硬件装配
    @return str
    """

    _bind_runtime_hw_bundle(runtime_state, hw_bundle)
    return _tick(runtime_state, now_ms=now_ms, cycle_token=cycle_token)


def apply_runtime_command(
    runtime_state,
    command,
    now_ms,
    cycle_token=None,
    hw_bundle=None,
):
    """执行一条辅车运行时命令

    @brief 对外统一收口命令入口, 保证命令执行前先完成硬件 owner 绑定。
    @param runtime_state 辅车运行时状态
    @param command 已解析命令
    @param now_ms 当前毫秒时间
    @param cycle_token 当前周期令牌
    @param hw_bundle 可选硬件装配
    @return str
    """

    _bind_runtime_hw_bundle(runtime_state, hw_bundle)
    return _apply_command(
        runtime_state,
        command,
        now_ms=now_ms,
        cycle_token=cycle_token,
    )
