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
