def test_motion_runtime_accepts_follow_command_and_updates_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    assert (
        runtime.apply_command(
            parse_command("follow=1,seq=7,valid=1,dx=0.10,dy=-0.05"),
            now_ms=1,
        )
        == "BUSY"
    )
    assert runtime.state.follow_active is True
    assert runtime.state.last_seq == 7
    assert runtime.state.state_label == "BUSY"
    assert runtime.state.velocity_command == (0.1, -0.05, 0.0)
    assert runtime.state.timeout is False


def test_motion_runtime_discards_duplicate_or_older_follow_packet() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    runtime.apply_command(
        parse_command("follow=1,seq=7,valid=1,dx=0.10,dy=0.00"),
        now_ms=1,
    )

    result = runtime.apply_command(
        parse_command("follow=1,seq=7,valid=1,dx=0.20,dy=0.10"),
        now_ms=2,
    )

    assert result == "IGNORED"
    assert runtime.state.last_seq == 7


def test_motion_runtime_marks_follow_inactive_when_target_missing() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    result = runtime.apply_command(
        parse_command("follow=1,seq=8,valid=0,dx=0.00,dy=0.00"),
        now_ms=2,
    )

    assert result == "HOLD"
    assert runtime.state.follow_active is False
    assert runtime.state.state_label == "IDLE"
    assert runtime.state.velocity_command == (0.0, 0.0, 0.0)
    assert runtime.tick(now_ms=3) == "ACK"


def test_motion_runtime_stops_when_timeout_expires() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )

    assert runtime.tick(now_ms=150) == "DONE"
    assert runtime.state.follow_active is False
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True
    assert runtime.state.last_error == "timeout_stop"


def test_motion_runtime_accepts_velocity_entry_as_base_chassis_capability() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    result = runtime.apply_command(parse_command("VEL 0.1 0.2 0.3"), now_ms=1)

    assert result == "BUSY"
    assert runtime.state.follow_active is True
    assert runtime.state.state_label == "BUSY"
    assert runtime.state.velocity_command[0] == 0.1
    assert runtime.state.velocity_command[1] == 0.2
    assert runtime.state.velocity_command[2] != 0.0
    assert runtime.state.last_error == ""


def test_motion_runtime_rejects_legacy_move_entry_in_current_stage() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    result = runtime.apply_command(parse_command("MOVE 0.1 0.2 15"), now_ms=1)

    assert result == "ERR"
    assert runtime.state.follow_active is False
    assert runtime.state.state_label == "IDLE"
    assert runtime.state.velocity_command == (0.0, 0.0, 0.0)
    assert runtime.state.last_error == "unsupported_command"


def test_motion_runtime_hold_does_not_clear_timeout_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"

    result = runtime.apply_command(parse_command("HOLD"), now_ms=151)

    assert result == "DONE"
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True
    assert runtime.state.last_error == "timeout_stop"


def test_motion_runtime_newer_follow_can_exit_timeout_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"

    result = runtime.apply_command(
        parse_command("follow=1,seq=9,valid=1,dx=0.1,dy=-0.1"), now_ms=151
    )

    assert result == "BUSY"
    assert runtime.state.state_label == "BUSY"
    assert runtime.state.timeout is False
    assert runtime.state.last_error == ""
    assert runtime.state.last_seq == 9


def test_motion_runtime_reset_odom_clears_timeout_but_keeps_last_seq() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"

    result = runtime.apply_command(parse_command("RESET_ODOM"), now_ms=151)

    assert result == "ACK"
    assert runtime.state.state_label == "IDLE"
    assert runtime.state.timeout is False
    assert runtime.state.last_error == ""
    assert runtime.state.last_seq == 8


def test_motion_runtime_stop_does_not_clear_timeout_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"

    result = runtime.apply_command(parse_command("STOP"), now_ms=151)

    assert result == "DONE"
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True
    assert runtime.state.last_error == "timeout_stop"


def test_motion_runtime_disarm_does_not_clear_timeout_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"

    result = runtime.apply_command(parse_command("DISARM"), now_ms=151)

    assert result == "ACK"
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True
    assert runtime.state.last_error == "timeout_stop"


def test_motion_runtime_ping_and_state_query_keep_current_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"

    ping_result = runtime.apply_command(parse_command("PING"), now_ms=151)
    state_line = runtime.apply_command(parse_command("STATE?"), now_ms=152)

    assert ping_result == "ACK"
    assert state_line == "state=1,state_label=TIMEOUT,last_seq=8,follow_active=0"
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True


def test_motion_runtime_tick_after_stop_keeps_timeout_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"
    assert runtime.apply_command(parse_command("STOP"), now_ms=151) == "DONE"

    tick_result = runtime.tick(now_ms=152)

    assert tick_result == "DONE"
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True
    assert runtime.state.last_error == "timeout_stop"


def test_motion_runtime_velocity_entry_refreshes_timeout_window() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )

    assert runtime.apply_command(parse_command("VEL 0.1 0.2 0.3"), now_ms=80) == "BUSY"
    assert runtime.tick(now_ms=110) == "BUSY"
    assert runtime.state.state_label == "BUSY"
    assert runtime.state.timeout is False


def test_motion_runtime_ignored_legacy_move_does_not_delay_timeout() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )

    assert runtime.apply_command(parse_command("MOVE 0.1 0.2 15"), now_ms=80) == "ERR"
    assert runtime.tick(now_ms=110) == "DONE"
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True


def test_motion_runtime_reset_odom_clears_velocity_command_but_keeps_last_seq() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=-0.1"), now_ms=10
    )

    result = runtime.apply_command(parse_command("RESET_ODOM"), now_ms=11)

    assert result == "ACK"
    assert runtime.state.state_label == "IDLE"
    assert runtime.state.velocity_command == (0.0, 0.0, 0.0)
    assert runtime.state.last_seq == 8


def test_motion_runtime_hold_does_not_retrigger_timeout_on_later_tick() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )
    assert runtime.tick(now_ms=150) == "DONE"

    assert runtime.apply_command(parse_command("HOLD"), now_ms=151) == "DONE"
    assert runtime.tick(now_ms=260) == "ACK"
    assert runtime.state.state_label == "TIMEOUT"
    assert runtime.state.timeout is True


def test_motion_runtime_reset_odom_does_not_start_new_timeout_window() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0"), now_ms=10
    )

    assert runtime.apply_command(parse_command("RESET_ODOM"), now_ms=20) == "ACK"
    assert runtime.tick(now_ms=130) == "ACK"
    assert runtime.state.state_label == "IDLE"
    assert runtime.state.timeout is False


def test_motion_runtime_vel_command_keeps_heading_hold_enabled_by_default() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    class FakeHeading:
        def heading_deg(self):
            return 15.0

    runtime = MotionRuntime(timeout_ms=100, hw_bundle={"imu": FakeHeading()})

    result = runtime.apply_command(parse_command("VEL 0.1 0.0 0.0"), now_ms=0)

    assert result == "BUSY"
    assert runtime.state.velocity_command[0] == 0.1
    assert runtime.state.velocity_command[1] == 0.0
    assert runtime.state.velocity_command[2] != 0.0


def test_motion_runtime_maps_follow_direction_to_motor_output_signs() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    class FakeMotor:
        def __init__(self) -> None:
            self.last_duty = 0

        def set_duty(self, duty) -> None:
            self.last_duty = int(duty)

        def stop(self) -> None:
            self.last_duty = 0

    class FakeHeading:
        def heading_deg(self):
            return 0.0

    motors = {"m": FakeMotor(), "l": FakeMotor(), "r": FakeMotor()}
    runtime = MotionRuntime(
        timeout_ms=100,
        hw_bundle={"motors": motors, "imu": FakeHeading()},
    )

    runtime.apply_command(
        parse_command("follow=1,seq=1,valid=1,dx=300.0,dy=0.0"),
        now_ms=0,
    )
    right_shift = {name: motor.last_duty for name, motor in motors.items()}

    runtime.apply_command(
        parse_command("follow=1,seq=2,valid=1,dx=0.0,dy=300.0"),
        now_ms=1,
    )
    forward_shift = {name: motor.last_duty for name, motor in motors.items()}

    assert right_shift["m"] == 0
    assert right_shift["l"] > 0
    assert right_shift["r"] < 0
    assert forward_shift["m"] < 0
    assert forward_shift["l"] > 0
    assert forward_shift["r"] > 0
