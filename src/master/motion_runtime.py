"""主车底座主数据链运行时.

@file src/master/motion_runtime.py
"""

_package_name = str(globals().get("__package__", ""))

_TRACE_PRINT_LIMIT = 40
_trace_print_count = 0


def _debug_print(stage, **payload):
    if not payload:
        print("[master.motion] %s" % str(stage))
        return
    parts = []
    for key in sorted(payload):
        parts.append("%s=%s" % (str(key), str(payload[key])))
    print("[master.motion] %s | %s" % (str(stage), ", ".join(parts)))


def _trace_control_chain(state):
    global _trace_print_count

    gyro_z_raw = float(state.imu_calibrated[5])
    omega_cmd = float(state.last_applied_target.get("omega", 0.0))
    motor_active = any(int(state.motor_duties[name]) != 0 for name in ("m", "l", "r"))
    wheel_target_active = any(
        abs(float(state.target_wheel_speeds[name])) > 1e-6 for name in ("m", "l", "r")
    )
    gyro_active = abs(gyro_z_raw) > 1e-6 or abs(float(state.yaw_rate_deg_s)) > 1e-6
    hold_active = abs(omega_cmd) > 1e-6
    if not (gyro_active or hold_active or wheel_target_active or motor_active):
        return
    if _trace_print_count >= _TRACE_PRINT_LIMIT:
        return
    _trace_print_count += 1
    _debug_print(
        "hold_trace",
        duty=dict(state.motor_duties),
        heading=round(float(state.heading_deg), 3),
        target_heading=round(float(state.target_heading_deg), 3),
        omega=round(omega_cmd, 3),
        wheel_now={
            name: round(float(state.wheel_speeds[name]), 3) for name in ("m", "l", "r")
        },
        wheel_target={
            name: round(float(state.target_wheel_speeds[name]), 3)
            for name in ("m", "l", "r")
        },
        yaw_integral=round(float(state.yaw_integral), 3),
        yaw_rate=round(float(state.yaw_rate_deg_s), 3),
        z_raw=round(gyro_z_raw, 3),
    )


if _package_name in ("", None):
    import config
    import runtime_params
    from ctrl.attitude import (
        HeadingEstimator,
        capture_heading_target,
        compute_heading_correction,
        update_heading_from_gyro,
    )
    from ctrl.filters import LowPassFilter, build_wheel_filter_bank, update_wheel_speeds
    from ctrl.kinematics import (
        build_kinematics,
        build_odometry,
        update_odometry_from_wheels,
    )
    from ctrl.pid import apply_wheel_speed_control, build_wheel_speed_controllers
    from state import MotionRuntimeState
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
        update_wheel_speeds,
    )
    from .ctrl.kinematics import (
        build_kinematics,
        build_odometry,
        update_odometry_from_wheels,
    )
    from .ctrl.pid import apply_wheel_speed_control, build_wheel_speed_controllers
    from .state import MotionRuntimeState


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


def _trace_ident_lookup_loaded(path, wheel_controllers):
    wheel_ident = {}
    for name in ("m", "l", "r"):
        controller = wheel_controllers.get(name)
        if controller is None:
            continue
        wheel_ident[name] = (
            float(controller.plant_gain or 0.0),
            float(controller.plant_tau or 0.0),
        )
    _debug_print(
        "ident_lookup_loaded",
        path=str(path),
        wheel_ident=wheel_ident,
    )


def _heading_chain_ready(hw_bundle):
    if hw_bundle is None:
        return False
    imu = hw_bundle.get("imu")
    if imu is None:
        return False
    return any(
        getattr(imu, name, None) is not None
        for name in ("read_calibrated", "heading_deg", "read_raw")
    )


def _encoder_chain_ready(hw_bundle):
    if hw_bundle is None:
        return False
    encoders = hw_bundle.get("encoders")
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


def base_chain_ready(hw_bundle):
    return _heading_chain_ready(hw_bundle) and _encoder_chain_ready(hw_bundle)


def _resolve_state_hw_bundle(state, hw_bundle):
    if hw_bundle is not None:
        state.hw_bundle = hw_bundle
        return hw_bundle
    return getattr(state, "hw_bundle", None)


def _state_imu_port(state, hw_bundle=None):
    resolved_hw_bundle = _resolve_state_hw_bundle(state, hw_bundle)
    if resolved_hw_bundle is None:
        return None
    return resolved_hw_bundle.get("imu")


def _state_encoder_bundle(state, hw_bundle=None):
    resolved_hw_bundle = _resolve_state_hw_bundle(state, hw_bundle)
    if resolved_hw_bundle is None:
        return None
    return resolved_hw_bundle.get("encoders")


def _state_motor_bundle(state, hw_bundle=None):
    resolved_hw_bundle = _resolve_state_hw_bundle(state, hw_bundle)
    if resolved_hw_bundle is None:
        return None
    return resolved_hw_bundle.get("motors")


def _read_imu_sample_for_state(state, hw_bundle=None):
    imu = _state_imu_port(state, hw_bundle=hw_bundle)
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


def _read_encoder_ticks_for_state(state, hw_bundle=None):
    encoders = _state_encoder_bundle(state, hw_bundle=hw_bundle)
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


def create_runtime_state(hw_bundle=None) -> MotionRuntimeState:
    pid_map = dict(runtime_params.PID_MAP)
    ident_lookup = _load_ident_lookup(config.IDENT_RESULTS_FILE)
    imu_offsets = _load_gyro_offsets(config.GYRO_OFFSET_FILE)
    state = MotionRuntimeState()
    state.hw_bundle = hw_bundle
    state.pid_map = pid_map
    state.heading_hold_enabled = True
    state.yaw_kp = float(runtime_params.YAW_KP)
    state.yaw_ki = float(runtime_params.YAW_KI)
    state.yaw_kd = float(runtime_params.YAW_KD)
    state.yaw_i_max = float(runtime_params.YAW_I_MAX)
    state.auto_omega_max = float(runtime_params.AUTO_OMEGA_MAX)
    state.hold_speed_eps = float(runtime_params.HOLD_SPEED_EPS)
    state.tick_ms = int(runtime_params.CONTROL_TICK_MS)
    state.tick_s = float(state.tick_ms) / 1000.0
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
    _trace_ident_lookup_loaded(config.IDENT_RESULTS_FILE, state.wheel_controllers)
    imu = _state_imu_port(state)
    if imu is not None:
        apply_offsets = getattr(imu, "apply_offsets", None)
        if apply_offsets is not None:
            apply_offsets(state.imu_offsets)
    return state


def next_motion_control_seq(state) -> int:
    state._control_seq += 1
    return int(state._control_seq)


def _resolve_applied_target_for_state(state, target, heading_deg):
    kind = str(target.get("kind", "hold"))
    if kind == "vel":
        vx = float(target.get("vx", 0.0))
        vy = float(target.get("vy", 0.0))
        manual_omega = float(target.get("omega", 0.0))
        if abs(manual_omega) >= float(state.hold_speed_eps):
            state.heading_deg = float(heading_deg)
            capture_heading_target(state)
            return {
                "kind": "vel",
                "vx": vx,
                "vy": vy,
                "omega": _clamp(
                    manual_omega, -state.auto_omega_max, state.auto_omega_max
                ),
            }
        return {
            "kind": "vel",
            "vx": vx,
            "vy": vy,
            "omega": compute_heading_correction(state, heading_deg),
        }
    return {
        "kind": "hold",
        "vx": 0.0,
        "vy": 0.0,
        "omega": compute_heading_correction(state, heading_deg),
    }


def _apply_motor_output_for_state(state, vx, vy, omega, hw_bundle=None):
    wheel_targets = state.kinematics.inverse_kinematics(
        float(vy), float(vx), float(omega)
    )
    motors = _state_motor_bundle(state, hw_bundle=hw_bundle)
    apply_wheel_speed_control(
        state,
        wheel_targets,
        limit=runtime_params.FOLLOW_OUTPUT_LIMIT,
        motors=motors,
    )


def apply_motion_target(state, target):
    previous_kind = str(getattr(state, "last_target", {}).get("kind", "hold"))
    state.last_target = dict(target)
    kind = str(state.last_target.get("kind", "hold"))
    if kind != "vel":
        state.last_target = {"kind": "hold"}
        if previous_kind == "vel" or not state.heading_target_ready:
            capture_heading_target(state)
    return dict(state.last_target)


def resolve_heading_hold_target_from_state(
    state, current_heading_deg, hw_bundle=None, cycle_token=None
):
    heading_deg = float(current_heading_deg)
    if _state_imu_port(state, hw_bundle=hw_bundle) is not None:
        run_base_cycle(state, hw_bundle=hw_bundle, cycle_token=cycle_token)
        heading_deg = float(state.heading_deg)
    else:
        state.heading_deg = heading_deg
    applied_target = _resolve_applied_target_for_state(
        state, state.last_target, heading_deg
    )
    state.last_applied_target = dict(applied_target)
    return applied_target


def run_motion_cycle(state, hw_bundle=None, cycle_token=None):
    run_base_cycle(state, hw_bundle=hw_bundle, cycle_token=cycle_token)
    applied_target = _resolve_applied_target_for_state(
        state,
        state.last_target,
        state.heading_deg,
    )
    state.last_applied_target = dict(applied_target)
    _apply_motor_output_for_state(
        state,
        applied_target.get("vx", 0.0),
        applied_target.get("vy", 0.0),
        applied_target.get("omega", 0.0),
        hw_bundle=hw_bundle,
    )
    _trace_control_chain(state)
    return {
        "target": dict(state.last_applied_target),
        "heading_est_deg": float(state.heading_deg),
        "yaw_rate_deg_s": float(state.yaw_rate_deg_s),
        "odom": (float(state.odom[0]), float(state.odom[1])),
    }


def run_base_cycle(state, hw_bundle=None, cycle_token=None) -> dict:
    resolved_hw_bundle = _resolve_state_hw_bundle(state, hw_bundle)
    if cycle_token is not None and cycle_token == getattr(
        state, "_last_cycle_token", None
    ):
        if getattr(state, "_last_base_snapshot", None) is None:
            return {}
        return dict(state._last_base_snapshot)

    heading_override = _read_imu_sample_for_state(state, hw_bundle=resolved_hw_bundle)
    update_heading_from_gyro(state, heading_override=heading_override)

    raw_ticks = _read_encoder_ticks_for_state(state, hw_bundle=resolved_hw_bundle)
    state.encoder_ticks = dict(raw_ticks)
    state.wheel_speeds = update_wheel_speeds(
        state.wheel_filters,
        raw_ticks,
        ("m", "l", "r"),
    )

    odom_x, odom_y = update_odometry_from_wheels(state)
    # 主车对外只返回底座观测快照, 不在这里混入视觉或调度阶段状态
    snapshot = {
        "imu_raw": tuple(state.imu_raw),
        "encoder_ticks": dict(state.encoder_ticks),
        "heading_est_deg": float(state.heading_deg),
        "odom": (float(state.odom[0]), float(state.odom[1])),
        "yaw_rate_deg_s": float(state.yaw_rate_deg_s),
        "base_ok": 1 if base_chain_ready(resolved_hw_bundle) else 0,
    }
    state._last_cycle_token = cycle_token
    state._last_base_snapshot = dict(snapshot)
    return snapshot


class MotionRuntime(MotionRuntimeState):
    """负责主车底座主数据链 owner.

    @brief 持有 IMU、编码器、里程和航向角保持链路, 供 app 在每个周期读取, 不承担视觉状态机职责。
    """

    def __init__(self, hw_bundle=None):
        state = create_runtime_state(hw_bundle=hw_bundle)
        self.__dict__.update(state.__dict__)

    def refresh_base_chain(self, cycle_token=None):
        return run_base_cycle(self, hw_bundle=self.hw_bundle, cycle_token=cycle_token)

    def apply_self_target(self, target):
        return apply_motion_target(self, target)

    def next_control_seq(self):
        return next_motion_control_seq(self)

    def update_heading_hold(self, current_heading_deg, cycle_token=None):
        return resolve_heading_hold_target_from_state(
            self,
            current_heading_deg,
            hw_bundle=self.hw_bundle,
            cycle_token=cycle_token,
        )

    def execute_control_loop(self, cycle_token=None):
        return run_motion_cycle(self, hw_bundle=self.hw_bundle, cycle_token=cycle_token)
