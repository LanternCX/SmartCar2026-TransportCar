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


def _load_ident_lookup(path):
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
    state.follow_target_world = (
        float(state.odom[0]) + float(offset_x),
        float(state.odom[1]) + float(offset_y),
    )


def _read_imu_sample(state):
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
    if cycle_token is not None and cycle_token == state._last_cycle_token:
        if state._last_base_snapshot is None:
            return {}
        return dict(state._last_base_snapshot)

    _update_base_ok(state)

    heading_override = _read_imu_sample(state)
    update_heading_from_gyro(state, heading_override=heading_override)
    has_valid_attitude_dt = float(state.tick_s) > 0.0

    raw_ticks = _read_encoder_ticks(state)
    state.encoder_ticks = dict(raw_ticks)
    if has_valid_attitude_dt:
        set_wheel_filter_dt_s(state.wheel_filters, ("m", "l", "r"), state.tick_s)
        state.wheel_speeds = update_wheel_speeds(
            state.wheel_filters,
            raw_ticks,
            ("m", "l", "r"),
        )
        odom_x, odom_y = update_odometry_from_wheels(state)
    else:
        set_wheel_filter_dt_s(state.wheel_filters, ("m", "l", "r"), 0.0)
        update_wheel_speeds(state.wheel_filters, raw_ticks, ())
        state.wheel_speeds = dict(state.wheel_speeds)
        odom_x = float(state.odom[0])
        odom_y = float(state.odom[1])
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
    wheel_targets = state.kinematics.inverse_kinematics(
        float(dy), float(dx), float(omega)
    )
    motors = _motor_bundle(state)
    if float(state.tick_s) <= 0.0:
        for name in ("m", "l", "r"):
            state.target_wheel_speeds[name] = 0.0
            state.motor_duties[name] = 0
        if motors is not None:
            for motor in motors.values():
                stop = getattr(motor, "stop", None)
                if stop is not None:
                    stop()
                else:
                    motor.set_duty(0)
        return {"m": 0.0, "l": 0.0, "r": 0.0}
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
    state.follow_active = False
    state.state_label = "TIMEOUT" if reason == "timeout_stop" else "IDLE"
    state.velocity_command = (0.0, 0.0, 0.0)
    state.timeout = reason == "timeout_stop"
    _clear_follow_target(state)
    capture_heading_target(state)
    _stop_motors(state)
    _mark_control_applied(state, cycle_token=cycle_token)
    if reason:
        state.last_error = reason


def _preserve_timeout_stop(state, cycle_token=None):
    _refresh_base_chain(state, cycle_token=cycle_token)
    state.follow_active = False
    state.velocity_command = (0.0, 0.0, 0.0)
    state.state_label = "TIMEOUT"
    state.timeout = True
    _clear_follow_target(state)
    capture_heading_target(state)
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
    _refresh_base_chain(state, cycle_token=cycle_token)
    if int(command.seq) <= int(state.last_seq):
        return "IGNORED"
    state.safety.mark_command(now_ms)
    state.safety.clear_estop()
    state.last_error = ""
    state.timeout = False
    state.last_seq = int(command.seq)
    if not command.valid:
        state.follow_active = False
        state.state_label = "IDLE"
        state.velocity_command = (0.0, 0.0, 0.0)
        _clear_follow_target(state)
        capture_heading_target(state)
        _stop_motors(state)
        _mark_control_applied(state, cycle_token=cycle_token)
        return "HOLD"
    state.follow_active = True
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
    if float(state.tick_s) <= 0.0:
        state.velocity_command = (0.0, 0.0, 0.0)
        _apply_motor_output(state, 0.0, 0.0, 0.0)
        _mark_control_applied(state, cycle_token=cycle_token)
        return "BUSY"
    control_dx, control_dy = resolve_follow_velocity(state)
    omega = compute_heading_correction(state)
    state.velocity_command = (control_dx, control_dy, omega)
    _apply_motor_output(state, control_dx, control_dy, omega)
    _mark_control_applied(state, cycle_token=cycle_token)
    return "BUSY"


def _apply_velocity(state, command, now_ms, cycle_token=None):
    _refresh_base_chain(state, cycle_token=cycle_token)
    state.safety.mark_command(now_ms)
    state.safety.clear_estop()
    state.last_error = ""
    state.timeout = False
    state.follow_active = True
    state.state_label = "BUSY"
    _clear_follow_target(state)
    if float(state.tick_s) <= 0.0:
        state.velocity_command = (0.0, 0.0, 0.0)
        _apply_motor_output(state, 0.0, 0.0, 0.0)
        _mark_control_applied(state, cycle_token=cycle_token)
        return "BUSY"
    manual_omega = float(command.omega)
    if abs(manual_omega) >= float(state.hold_speed_eps):
        capture_heading_target(state)
        limited_omega = _clamp(
            manual_omega, -state.auto_omega_max, state.auto_omega_max
        )
    else:
        limited_omega = compute_heading_correction(state)
    state.velocity_command = (float(command.vx), float(command.vy), limited_omega)
    _apply_motor_output(
        state,
        state.velocity_command[0],
        state.velocity_command[1],
        state.velocity_command[2],
    )
    _mark_control_applied(state, cycle_token=cycle_token)
    return "BUSY"


def _apply_command(state, command, now_ms, cycle_token=None):
    if command.kind == "ping":
        return "ACK"
    if command.kind == "state_query":
        return state.state_line()
    if command.kind == "follow":
        return _apply_follow(state, command, now_ms, cycle_token=cycle_token)
    if command.kind == "arm":
        _refresh_base_chain(state, cycle_token=cycle_token)
        capture_heading_target(state)
        return "ACK"
    if command.kind == "disarm":
        _clear_follow_deadline(state)
        if _is_timeout_locked(state):
            _preserve_timeout_stop(state, cycle_token=cycle_token)
        else:
            _stop(state, cycle_token=cycle_token)
        return "ACK"
    if command.kind == "stop":
        state.safety.trigger_estop()
        if _is_timeout_locked(state):
            _preserve_timeout_stop(state, cycle_token=cycle_token)
        else:
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
        state.follow_active = False
        state.state_label = "IDLE"
        state.velocity_command = (0.0, 0.0, 0.0)
        state.timeout = False
        state.last_error = ""
        _clear_follow_target(state)
        capture_heading_target(state)
        _stop_motors(state)
        _mark_control_applied(state, cycle_token=cycle_token)
        state.safety.clear_estop()
        return "ACK"
    if command.kind == "hold":
        _clear_follow_deadline(state)
        should_refresh_heading_target = bool(state.follow_active) or not bool(
            state.heading_target_ready
        )
        state.follow_active = False
        if not _is_timeout_locked(state):
            state.state_label = "IDLE"
        state.velocity_command = (0.0, 0.0, 0.0)
        _clear_follow_target(state)
        if should_refresh_heading_target:
            capture_heading_target(state)
        _stop_motors(state)
        _mark_control_applied(state, cycle_token=cycle_token)
        state.safety.clear_estop()
        return "DONE"
    if command.kind == "vel":
        return _apply_velocity(state, command, now_ms, cycle_token=cycle_token)
    if command.kind == "move":
        return _reject_unsupported_command(state, cycle_token=cycle_token)
    return _reject_unsupported_command(state, cycle_token=cycle_token)


def _tick(state, now_ms, cycle_token=None):
    _refresh_base_chain(state, cycle_token=cycle_token)
    if state.safety.should_stop(now_ms):
        if _is_timeout_locked(state):
            _preserve_timeout_stop(state, cycle_token=cycle_token)
        else:
            reason = "estop" if state.safety.estop_active else "timeout_stop"
            _stop(state, reason, cycle_token=cycle_token)
        return "DONE"
    if _control_already_applied(state, cycle_token=cycle_token):
        return "BUSY" if state.follow_active else "ACK"
    if state.follow_active:
        if float(state.tick_s) <= 0.0:
            state.velocity_command = (0.0, 0.0, 0.0)
            _apply_motor_output(state, 0.0, 0.0, 0.0)
            _mark_control_applied(state, cycle_token=cycle_token)
            return "BUSY"
        dx, dy = resolve_follow_velocity(state)
        omega = compute_heading_correction(state)
        state.velocity_command = (dx, dy, omega)
        _apply_motor_output(state, dx, dy, omega)
        _mark_control_applied(state, cycle_token=cycle_token)
        return "BUSY"
    if float(state.tick_s) <= 0.0:
        state.velocity_command = (0.0, 0.0, 0.0)
        _apply_motor_output(state, 0.0, 0.0, 0.0)
        _mark_control_applied(state, cycle_token=cycle_token)
        return "ACK"
    _apply_motor_output(state, 0.0, 0.0, compute_heading_correction(state))
    _mark_control_applied(state, cycle_token=cycle_token)
    return "ACK"


def create_runtime_state(timeout_ms=None, hw_bundle=None):
    pid_map = dict(runtime_params.PID_MAP)
    ident_lookup = _load_ident_lookup(config.IDENT_RESULTS_FILE)
    imu_offsets = _load_gyro_offsets(config.GYRO_OFFSET_FILE)
    if timeout_ms is None:
        timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
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
    _bind_runtime_hw_bundle(runtime_state, hw_bundle)
    return _tick(runtime_state, now_ms=now_ms, cycle_token=cycle_token)


def apply_runtime_command(
    runtime_state,
    command,
    now_ms,
    cycle_token=None,
    hw_bundle=None,
):
    _bind_runtime_hw_bundle(runtime_state, hw_bundle)
    return _apply_command(
        runtime_state,
        command,
        now_ms=now_ms,
        cycle_token=cycle_token,
    )
