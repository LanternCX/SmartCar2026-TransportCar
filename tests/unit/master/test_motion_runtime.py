def test_master_motion_runtime_tracks_latest_self_target() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    target = {"kind": "hold"}

    result = runtime.apply_self_target(target)

    assert result == target
    assert runtime.last_target == target


def test_master_motion_runtime_allocates_monotonic_follow_sequence() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    assert runtime.next_control_seq() == 1
    assert runtime.next_control_seq() == 2


def test_master_motion_runtime_reads_yaw_runtime_params() -> None:
    import master.runtime_params as runtime_params
    from master.motion_runtime import MotionRuntime

    old_kp = runtime_params.YAW_KP
    runtime_params.YAW_KP = 0.42
    try:
        runtime = MotionRuntime()
    finally:
        runtime_params.YAW_KP = old_kp

    assert runtime.yaw_kp == 0.42


def test_master_motion_runtime_reads_yaw_stability_params() -> None:
    import master.runtime_params as runtime_params
    from master.motion_runtime import MotionRuntime

    old_kd = getattr(runtime_params, "YAW_KD", None)
    old_eps = getattr(runtime_params, "HOLD_SPEED_EPS", None)
    setattr(runtime_params, "YAW_KD", 0.08)
    setattr(runtime_params, "HOLD_SPEED_EPS", 0.25)
    try:
        runtime = MotionRuntime()
    finally:
        if old_kd is None:
            delattr(runtime_params, "YAW_KD")
        else:
            setattr(runtime_params, "YAW_KD", old_kd)
        if old_eps is None:
            delattr(runtime_params, "HOLD_SPEED_EPS")
        else:
            setattr(runtime_params, "HOLD_SPEED_EPS", old_eps)

    assert getattr(runtime, "yaw_kd") == 0.08
    assert getattr(runtime, "hold_speed_eps") == 0.25


def test_master_motion_runtime_builds_dual_window_wheel_filter_tail() -> None:
    from master.ctrl.filters import DualWindowRegressionFilter
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    assert isinstance(runtime.wheel_filters["m"].tail, DualWindowRegressionFilter)


def test_master_motion_runtime_logs_loaded_ident_lookup(monkeypatch) -> None:
    import master.motion_runtime as runtime

    captured = []
    ident_lookup = {
        "m": (0.00055, 0.01),
        "l": (0.000581, 0.01),
        "r": (0.000551, 0.01),
    }

    monkeypatch.setattr(runtime, "_load_ident_lookup", lambda path: dict(ident_lookup))
    monkeypatch.setattr(runtime, "_load_gyro_offsets", lambda path: (0.0,) * 6)
    monkeypatch.setattr(
        runtime,
        "_debug_print",
        lambda stage, **payload: captured.append((stage, dict(payload))),
    )

    runtime.create_runtime_state(hw_bundle=None)

    assert (
        "ident_lookup_loaded",
        {
            "path": runtime.config.IDENT_RESULTS_FILE,
            "wheel_ident": ident_lookup,
        },
    ) in captured


def test_master_motion_runtime_execute_loop_no_longer_traces_each_cycle(
    monkeypatch,
) -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    calls = {"count": 0}

    monkeypatch.setattr(
        "master.motion_runtime._trace_control_chain",
        lambda state: calls.__setitem__("count", calls["count"] + 1),
    )

    runtime.execute_control_loop(cycle_token=object())

    assert calls["count"] == 0


def test_master_motion_runtime_keeps_heading_hold_enabled_by_default() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    assert runtime.heading_hold_enabled is True


def test_master_motion_runtime_heading_hold_output_changes_with_heading_error() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    runtime.apply_self_target({"kind": "vel", "vx": 0.1, "vy": 0.0, "omega": 0.0})

    output = runtime.update_heading_hold(current_heading_deg=15.0)

    assert output["kind"] == "vel"
    assert output["vx"] == 0.1
    assert output["vy"] == 0.0
    assert output["omega"] != 0.0


def test_master_motion_runtime_closes_speed_loop_before_motor_output() -> None:
    from master.motion_runtime import MotionRuntime

    class FakeMotor:
        def __init__(self) -> None:
            self.last_duty = 0

        def set_duty(self, duty) -> None:
            self.last_duty = int(duty)

    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeEncoder:
        def __init__(self, values) -> None:
            self.values = list(values)
            self.index = 0

        def read_and_clear(self):
            value = self.values[min(self.index, len(self.values) - 1)]
            self.index += 1
            return value

    motors_static = {name: FakeMotor() for name in ("m", "l", "r")}
    motors_feedback = {name: FakeMotor() for name in ("m", "l", "r")}
    runtime_static = MotionRuntime(
        hw_bundle={
            "motors": motors_static,
            "encoders": {name: FakeEncoder((0.0, 0.0)) for name in ("m", "l", "r")},
            "imu": FakeHeading(),
        }
    )
    runtime_feedback = MotionRuntime(
        hw_bundle={
            "motors": motors_feedback,
            "encoders": {
                "m": FakeEncoder((0.0, -1.0)),
                "l": FakeEncoder((0.0, 0.5)),
                "r": FakeEncoder((0.0, 0.5)),
            },
            "imu": FakeHeading(),
        }
    )

    for runtime in (runtime_static, runtime_feedback):
        runtime.apply_self_target({"kind": "vel", "vx": 0.0, "vy": 1.5, "omega": 0.0})
        runtime.execute_control_loop(cycle_token=object())
        runtime.execute_control_loop(cycle_token=object())

    static_duty = {name: motor.last_duty for name, motor in motors_static.items()}
    feedback_duty = {name: motor.last_duty for name, motor in motors_feedback.items()}

    assert feedback_duty != static_duty


def test_master_motion_runtime_defaults_heading_hold_to_current_heading() -> None:
    from master.motion_runtime import MotionRuntime

    class FakeHeading:
        def heading_deg(self):
            return 37.5

    runtime = MotionRuntime(hw_bundle={"imu": FakeHeading()})

    result = runtime.execute_control_loop(cycle_token=object())

    assert runtime.target_heading_deg == 37.5
    assert result["target"]["kind"] == "hold"
    assert result["target"]["omega"] == 0.0


def test_master_motion_runtime_repeated_hold_does_not_reset_target_heading() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    runtime.heading_deg = 12.0
    runtime.target_heading_deg = 12.0
    runtime.heading_target_ready = True

    runtime.heading_deg = 27.0
    runtime.apply_self_target({"kind": "hold"})

    assert runtime.target_heading_deg == 12.0


def test_master_motion_runtime_active_omega_bypasses_heading_hold() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    runtime.heading_deg = 27.0
    runtime.target_heading_deg = 12.0
    runtime.heading_target_ready = True
    runtime.yaw_integral = 9.0

    runtime.apply_self_target({"kind": "vel", "vx": 0.0, "vy": 0.0, "omega": 3.0})
    applied = runtime.update_heading_hold(current_heading_deg=27.0)

    assert applied["omega"] == 3.0
    assert runtime.target_heading_deg == 27.0
    assert runtime.yaw_integral == 0.0


def test_master_motion_runtime_small_manual_omega_falls_back_to_heading_hold() -> None:
    import pytest

    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    runtime.heading_deg = 27.0
    runtime.target_heading_deg = 12.0
    runtime.heading_target_ready = True
    runtime.yaw_integral = 0.0
    runtime.yaw_kp = 0.16
    runtime.yaw_ki = 0.1
    runtime.yaw_kd = 0.0
    runtime.tick_s = 0.005
    setattr(runtime, "hold_speed_eps", 0.25)

    runtime.apply_self_target({"kind": "vel", "vx": 0.0, "vy": 0.0, "omega": 0.1})
    applied = runtime.update_heading_hold(current_heading_deg=27.0)

    assert applied["omega"] == pytest.approx(-2.4075)
    assert runtime.target_heading_deg == 12.0


def test_master_motion_runtime_execute_loop_hands_back_to_hold_after_manual_turn() -> (
    None
):
    import pytest

    from master.motion_runtime import MotionRuntime

    class FakeHeading:
        def __init__(self) -> None:
            self.value = 27.0

        def heading_deg(self):
            return self.value

    imu = FakeHeading()
    runtime = MotionRuntime(hw_bundle={"imu": imu})
    runtime.target_heading_deg = 12.0
    runtime.heading_target_ready = True
    runtime.yaw_integral = 9.0
    runtime.hold_speed_eps = 0.25

    runtime.apply_self_target({"kind": "vel", "vx": 0.0, "vy": 0.0, "omega": 3.0})
    first = runtime.execute_control_loop(cycle_token=1)

    runtime.apply_self_target({"kind": "vel", "vx": 0.0, "vy": 0.0, "omega": 0.1})
    second = runtime.execute_control_loop(cycle_token=2)

    assert first["target"]["omega"] == 3.0
    assert runtime.target_heading_deg == 27.0
    assert second["target"]["omega"] == pytest.approx(0.0)


def test_master_motion_runtime_passes_dynamic_tick_to_speed_loop(monkeypatch) -> None:
    import pytest

    import master.ctrl.attitude as attitude
    from master.motion_runtime import MotionRuntime

    class FakeImu:
        def read_calibrated(self):
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    class FakeController:
        def __init__(self) -> None:
            self.dt_values = []

        def update(self, _target, _now, dt_s):
            self.dt_values.append(float(dt_s))
            return 0.0

        def reset(self):
            return None

    runtime = MotionRuntime(
        hw_bundle={
            "imu": FakeImu(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        }
    )
    controllers = {name: FakeController() for name in ("m", "l", "r")}
    runtime.wheel_controllers = controllers
    runtime.target_heading_deg = 30.0
    runtime.heading_target_ready = True
    runtime.last_target = {"kind": "hold"}
    runtime.last_attitude_time_us = 1_000_000

    monkeypatch.setattr(attitude, "_read_now_us", lambda: 1_012_345)

    runtime.execute_control_loop(cycle_token=object())

    assert runtime.tick_s == pytest.approx(0.012345)
    for controller in controllers.values():
        assert controller.dt_values == [pytest.approx(0.012345)]


def test_master_motion_runtime_zero_tick_falls_back_to_fixed_control_step(
    monkeypatch,
) -> None:
    import master.runtime_params as runtime_params
    import master.motion_runtime as runtime_module
    from master.motion_runtime import MotionRuntime

    class FakeImu:
        def read_calibrated(self):
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    class FakeController:
        def __init__(self) -> None:
            self.dt_values = []

        def update(self, _target, _now, dt_s):
            self.dt_values.append(float(dt_s))
            return 0.0

        def reset(self):
            return None

    motion_runtime = MotionRuntime(
        hw_bundle={
            "imu": FakeImu(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        }
    )
    controllers = {name: FakeController() for name in ("m", "l", "r")}
    motion_runtime.wheel_controllers = controllers
    motion_runtime.target_heading_deg = 0.0
    motion_runtime.heading_target_ready = True
    motion_runtime.last_target = {"kind": "hold"}
    motion_runtime.last_attitude_time_us = 1_000_000

    monkeypatch.setattr(
        runtime_module,
        "update_heading_from_gyro",
        lambda state, heading_override=None: setattr(state, "tick_s", 0.0),
    )
    monkeypatch.setattr(
        runtime_module,
        "update_wheel_speeds",
        lambda _filter_bank, _raw_ticks, wheel_names: {
            name: 0.0 for name in wheel_names
        },
    )
    monkeypatch.setattr(
        runtime_module,
        "update_odometry_from_wheels",
        lambda state, heading_deg=None: (0.0, 0.0),
    )

    motion_runtime.execute_control_loop(cycle_token=object())

    expected_dt = float(runtime_params.CONTROL_TICK_MS) / 1000.0
    for controller in controllers.values():
        assert controller.dt_values == [expected_dt]


def test_master_motion_runtime_accumulates_odometry_with_heading_before_update(
    monkeypatch,
) -> None:
    import master.motion_runtime as runtime

    class FakeImu:
        def read_calibrated(self):
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    state = runtime.create_runtime_state(
        hw_bundle={
            "imu": FakeImu(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        }
    )
    state.heading_deg = 0.0
    setattr(
        state.kinematics, "velocity_pulses_to_m_s", lambda pulses, dt_s: float(pulses)
    )
    setattr(state.kinematics, "forward_kinematics", lambda vm, vl, vr: (1.0, 0.0, 0.0))

    captured = {"heading_rad": 999.0}

    def _fake_update_heading(state, heading_override=None):
        state.heading_deg = 90.0

    def _fake_update_wheel_speeds(_filter_bank, _raw_ticks, wheel_names):
        return {name: 0.0 for name in wheel_names}

    def _fake_read_imu_sample_for_state(state, hw_bundle=None):
        return None

    def _fake_read_encoder_ticks_for_state(state, hw_bundle=None):
        return {name: 0.0 for name in ("m", "l", "r")}

    def _fake_odometry_update(vx_robot, vy_robot, heading_rad, dt_s):
        captured["heading_rad"] = float(heading_rad)
        return (0.0, 0.0)

    setattr(state.odometry, "update", _fake_odometry_update)

    monkeypatch.setattr(runtime, "update_heading_from_gyro", _fake_update_heading)
    monkeypatch.setattr(runtime, "update_wheel_speeds", _fake_update_wheel_speeds)
    monkeypatch.setattr(
        runtime, "_read_imu_sample_for_state", _fake_read_imu_sample_for_state
    )
    monkeypatch.setattr(
        runtime, "_read_encoder_ticks_for_state", _fake_read_encoder_ticks_for_state
    )

    runtime.run_base_cycle(state, hw_bundle=state.hw_bundle, cycle_token=object())

    assert captured["heading_rad"] == 0.0
    assert state.heading_deg == 90.0


def test_master_motion_runtime_zero_tick_skips_odometry_accumulation(
    monkeypatch,
) -> None:
    import master.motion_runtime as runtime

    class FakeImu:
        def read_calibrated(self):
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    state = runtime.create_runtime_state(
        hw_bundle={
            "imu": FakeImu(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        }
    )
    state.odom = [1.5, -0.5]

    monkeypatch.setattr(
        runtime,
        "update_heading_from_gyro",
        lambda state, heading_override=None: setattr(state, "tick_s", 0.0),
    )
    monkeypatch.setattr(
        runtime,
        "update_wheel_speeds",
        lambda _filter_bank, _raw_ticks, wheel_names: {
            name: 0.0 for name in wheel_names
        },
    )
    monkeypatch.setattr(
        runtime,
        "update_odometry_from_wheels",
        lambda state, heading_deg=None: (_ for _ in ()).throw(
            AssertionError("零周期不应继续推进里程累计")
        ),
    )

    snapshot = runtime.run_base_cycle(
        state, hw_bundle=state.hw_bundle, cycle_token=object()
    )

    assert snapshot["odom"] == (1.5, -0.5)
    assert tuple(state.odom) == (1.5, -0.5)


def test_master_motion_runtime_base_ok_requires_heading_and_encoder_chain() -> None:
    from master.motion_runtime import MotionRuntime

    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    missing_base_runtime = MotionRuntime(hw_bundle={"imu": FakeHeading()})
    complete_runtime = MotionRuntime(
        hw_bundle={
            "imu": FakeHeading(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        }
    )

    missing_snapshot = missing_base_runtime.refresh_base_chain(cycle_token=object())
    complete_snapshot = complete_runtime.refresh_base_chain(cycle_token=object())

    assert missing_snapshot["base_ok"] == 0
    assert complete_snapshot["base_ok"] == 1
