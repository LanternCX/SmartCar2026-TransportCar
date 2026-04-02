import pytest

from assistant.motion_runtime import (
    apply_runtime_command,
    create_runtime_state,
    run_base_cycle,
)
from assistant.protocol import parse_command


def _new_state(timeout_ms=100, hw_bundle=None):
    return create_runtime_state(timeout_ms=timeout_ms, hw_bundle=hw_bundle)


def _apply_line(state, line, now_ms, cycle_token=None, hw_bundle=None):
    return apply_runtime_command(
        state,
        parse_command(line),
        now_ms=now_ms,
        cycle_token=cycle_token,
        hw_bundle=hw_bundle,
    )


def _tick(state, now_ms, cycle_token=None, hw_bundle=None):
    return run_base_cycle(
        state,
        now_ms=now_ms,
        cycle_token=cycle_token,
        hw_bundle=hw_bundle,
    )


def test_motion_runtime_accepts_follow_command_and_updates_state() -> None:
    state = _new_state(timeout_ms=100)

    assert (
        _apply_line(
            state,
            "follow=1,seq=7,valid=1,dx=0.10,dy=-0.05",
            now_ms=1,
        )
        == "BUSY"
    )
    assert state.follow_active is True
    assert state.last_seq == 7
    assert state.state_label == "BUSY"
    assert state.velocity_command == (0.1, -0.05, 0.0)
    assert state.timeout is False


def test_motion_runtime_discards_duplicate_or_older_follow_packet() -> None:
    state = _new_state(timeout_ms=100)

    _apply_line(state, "follow=1,seq=7,valid=1,dx=0.10,dy=0.00", now_ms=1)

    result = _apply_line(state, "follow=1,seq=7,valid=1,dx=0.20,dy=0.10", now_ms=2)

    assert result == "IGNORED"
    assert state.last_seq == 7


def test_motion_runtime_marks_follow_inactive_when_target_missing() -> None:
    state = _new_state(timeout_ms=100)

    result = _apply_line(state, "follow=1,seq=8,valid=0,dx=0.00,dy=0.00", now_ms=2)

    assert result == "HOLD"
    assert state.follow_active is False
    assert state.state_label == "IDLE"
    assert state.velocity_command == (0.0, 0.0, 0.0)
    assert _tick(state, now_ms=3) == "ACK"


def test_motion_runtime_stops_when_timeout_expires() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)

    assert _tick(state, now_ms=150) == "DONE"
    assert state.follow_active is False
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_accepts_velocity_entry_as_base_chassis_capability() -> None:
    state = _new_state(timeout_ms=100)

    result = _apply_line(state, "VEL 0.1 0.2 0.3", now_ms=1)

    assert result == "BUSY"
    assert state.follow_active is True
    assert state.state_label == "BUSY"
    assert state.velocity_command[0] == 0.1
    assert state.velocity_command[1] == 0.2
    assert state.velocity_command[2] != 0.0
    assert state.last_error == ""


def test_motion_runtime_rejects_legacy_move_entry_in_current_stage() -> None:
    state = _new_state(timeout_ms=100)

    result = _apply_line(state, "MOVE 0.1 0.2 15", now_ms=1)

    assert result == "ERR"
    assert state.follow_active is False
    assert state.state_label == "IDLE"
    assert state.velocity_command == (0.0, 0.0, 0.0)
    assert state.last_error == "unsupported_command"


def test_motion_runtime_hold_does_not_clear_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "HOLD", now_ms=151)

    assert result == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_newer_follow_can_exit_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "follow=1,seq=9,valid=1,dx=0.1,dy=-0.1", now_ms=151)

    assert result == "BUSY"
    assert state.state_label == "BUSY"
    assert state.timeout is False
    assert state.last_error == ""
    assert state.last_seq == 9


def test_motion_runtime_reset_odom_clears_timeout_but_keeps_last_seq() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "RESET_ODOM", now_ms=151)

    assert result == "ACK"
    assert state.state_label == "IDLE"
    assert state.timeout is False
    assert state.last_error == ""
    assert state.last_seq == 8


def test_motion_runtime_stop_does_not_clear_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "STOP", now_ms=151)

    assert result == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_disarm_does_not_clear_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "DISARM", now_ms=151)

    assert result == "ACK"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_ping_and_state_query_keep_current_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    ping_result = _apply_line(state, "PING", now_ms=151)
    state_line = _apply_line(state, "STATE?", now_ms=152)

    assert ping_result == "ACK"
    assert state_line.startswith(
        "state=1,state_label=TIMEOUT,last_seq=8,follow_active=0,"
    )
    assert "base_ok=0" in state_line
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True


def test_motion_runtime_tick_after_stop_keeps_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"
    assert _apply_line(state, "STOP", now_ms=151) == "DONE"

    tick_result = _tick(state, now_ms=152)

    assert tick_result == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_velocity_entry_refreshes_timeout_window() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)

    assert _apply_line(state, "VEL 0.1 0.2 0.3", now_ms=80) == "BUSY"
    assert _tick(state, now_ms=110) == "BUSY"
    assert state.state_label == "BUSY"
    assert state.timeout is False


def test_motion_runtime_ignored_legacy_move_does_not_delay_timeout() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)

    assert _apply_line(state, "MOVE 0.1 0.2 15", now_ms=80) == "ERR"
    assert _tick(state, now_ms=110) == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True


def test_motion_runtime_reset_odom_clears_velocity_command_but_keeps_last_seq() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=-0.1", now_ms=10)

    result = _apply_line(state, "RESET_ODOM", now_ms=11)

    assert result == "ACK"
    assert state.state_label == "IDLE"
    assert state.velocity_command == (0.0, 0.0, 0.0)
    assert state.last_seq == 8


def test_motion_runtime_hold_does_not_retrigger_timeout_on_later_tick() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    assert _apply_line(state, "HOLD", now_ms=151) == "DONE"
    assert _tick(state, now_ms=260) == "ACK"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True


def test_motion_runtime_reset_odom_does_not_start_new_timeout_window() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "follow=1,seq=8,valid=1,dx=0.2,dy=0.0", now_ms=10)

    assert _apply_line(state, "RESET_ODOM", now_ms=20) == "ACK"
    assert _tick(state, now_ms=130) == "ACK"
    assert state.state_label == "IDLE"
    assert state.timeout is False


def test_motion_runtime_vel_command_keeps_heading_hold_enabled_by_default() -> None:
    class FakeHeading:
        def heading_deg(self):
            return 15.0

    state = _new_state(timeout_ms=100, hw_bundle={"imu": FakeHeading()})

    result = _apply_line(state, "VEL 0.1 0.0 0.0", now_ms=0)

    assert result == "BUSY"
    assert state.velocity_command[0] == 0.1
    assert state.velocity_command[1] == 0.0
    assert state.target_heading_deg == 15.0
    assert state.velocity_command[2] == 0.0


def test_motion_runtime_maps_follow_direction_to_motor_output_signs() -> None:
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
    state = _new_state(
        timeout_ms=100,
        hw_bundle={"motors": motors, "imu": FakeHeading()},
    )

    _apply_line(state, "follow=1,seq=1,valid=1,dx=300.0,dy=0.0", now_ms=0)
    right_shift = {name: motor.last_duty for name, motor in motors.items()}

    _apply_line(state, "follow=1,seq=2,valid=1,dx=0.0,dy=300.0", now_ms=1)
    forward_shift = {name: motor.last_duty for name, motor in motors.items()}

    assert right_shift["m"] == 0
    assert right_shift["l"] > 0
    assert right_shift["r"] < 0
    assert forward_shift["m"] < 0
    assert forward_shift["l"] > 0
    assert forward_shift["r"] > 0


def test_motion_runtime_reuses_same_cycle_sensor_snapshot() -> None:
    class FakeImu:
        def __init__(self) -> None:
            self.read_count = 0
            self.last_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        def read_calibrated(self):
            self.read_count += 1
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    class FakeEncoder:
        def __init__(self) -> None:
            self.read_count = 0

        def read_and_clear(self):
            self.read_count += 1
            return 12

    imu = FakeImu()
    encoders = {name: FakeEncoder() for name in ("m", "l", "r")}
    state = _new_state(timeout_ms=100, hw_bundle={"imu": imu, "encoders": encoders})
    cycle_token = object()

    _apply_line(
        state,
        "follow=1,seq=1,valid=1,dx=0.1,dy=0.0",
        now_ms=10,
        cycle_token=cycle_token,
    )
    _tick(state, now_ms=10, cycle_token=cycle_token)

    assert imu.read_count == 1
    assert all(port.read_count == 1 for port in encoders.values())


def test_motion_runtime_closes_speed_loop_before_motor_output() -> None:
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
    state_static = _new_state(
        timeout_ms=100,
        hw_bundle={
            "motors": motors_static,
            "encoders": {name: FakeEncoder((0.0, 0.0)) for name in ("m", "l", "r")},
            "imu": FakeHeading(),
        },
    )
    state_feedback = _new_state(
        timeout_ms=100,
        hw_bundle={
            "motors": motors_feedback,
            "encoders": {
                "m": FakeEncoder((0.0, -1.0)),
                "l": FakeEncoder((0.0, 0.5)),
                "r": FakeEncoder((0.0, 0.5)),
            },
            "imu": FakeHeading(),
        },
    )

    for state in (state_static, state_feedback):
        _apply_line(
            state,
            "follow=1,seq=1,valid=1,dx=0.0,dy=1.5",
            now_ms=0,
            cycle_token=object(),
        )
        _tick(state, now_ms=1, cycle_token=object())

    static_duty = {name: motor.last_duty for name, motor in motors_static.items()}
    feedback_duty = {name: motor.last_duty for name, motor in motors_feedback.items()}

    assert feedback_duty != static_duty


def test_motion_runtime_defaults_heading_hold_to_current_heading() -> None:
    class FakeHeading:
        def heading_deg(self):
            return 28.0

    state = _new_state(timeout_ms=100, hw_bundle={"imu": FakeHeading()})

    reply = _apply_line(
        state,
        "follow=1,seq=1,valid=1,dx=0.1,dy=0.0",
        now_ms=0,
        cycle_token=object(),
    )

    assert reply == "BUSY"
    assert state.target_heading_deg == 28.0
    assert state.velocity_command[2] == 0.0


def test_motion_runtime_same_cycle_does_not_apply_control_twice() -> None:
    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeMotor:
        def __init__(self) -> None:
            self.calls = 0

        def set_duty(self, duty) -> None:
            self.calls += 1

        def stop(self) -> None:
            self.calls += 1

    motors = {name: FakeMotor() for name in ("m", "l", "r")}
    state = _new_state(
        timeout_ms=100,
        hw_bundle={"imu": FakeHeading(), "motors": motors},
    )
    cycle_token = object()

    _apply_line(
        state,
        "follow=1,seq=1,valid=1,dx=0.1,dy=0.0",
        now_ms=0,
        cycle_token=cycle_token,
    )
    _tick(state, now_ms=0, cycle_token=cycle_token)

    assert all(motor.calls == 1 for motor in motors.values())


def test_motion_runtime_follow_rebinds_to_world_target_instead_of_raw_output() -> None:
    class FakeHeading:
        def __init__(self) -> None:
            self.values = [90.0, 0.0]
            self.index = 0

        def heading_deg(self):
            value = self.values[min(self.index, len(self.values) - 1)]
            self.index += 1
            return value

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    state = _new_state(
        timeout_ms=100,
        hw_bundle={
            "imu": FakeHeading(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        },
    )

    _apply_line(
        state,
        "follow=1,seq=1,valid=1,dx=1.0,dy=0.0",
        now_ms=0,
        cycle_token=object(),
    )
    first_command = state.velocity_command

    _tick(state, now_ms=5, cycle_token=object())

    assert first_command[:2] == (1.0, 0.0)
    assert state.velocity_command[0] == pytest.approx(0.0, abs=1e-6)
    assert state.velocity_command[1] == pytest.approx(-1.0, abs=1e-6)


def test_motion_runtime_base_ok_requires_heading_and_encoder_chain() -> None:
    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    missing_base_state = _new_state(timeout_ms=100, hw_bundle={"imu": FakeHeading()})
    complete_state = _new_state(
        timeout_ms=100,
        hw_bundle={
            "imu": FakeHeading(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        },
    )

    _tick(missing_base_state, now_ms=0)
    _tick(complete_state, now_ms=0)

    assert missing_base_state.base_ok is False
    assert complete_state.base_ok is True


def test_motion_runtime_state_query_exposes_real_base_ok() -> None:
    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    state = _new_state(
        timeout_ms=100,
        hw_bundle={
            "imu": FakeHeading(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        },
    )

    line = _apply_line(state, "STATE?", now_ms=0)

    assert "base_ok=0" in line
    _tick(state, now_ms=1)
    line = _apply_line(state, "STATE?", now_ms=2)
    assert "base_ok=1" in line
