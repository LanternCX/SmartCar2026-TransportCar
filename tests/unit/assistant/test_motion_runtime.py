import pytest

from assistant.motion_runtime import (
    apply_runtime_command,
    create_runtime_state,
    run_base_cycle,
)
from assistant.protocol import parse_command


def test_assistant_motion_runtime_imports_without_types_module(monkeypatch) -> None:
    import builtins
    import importlib
    import sys

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "types":
            raise ImportError("no module named 'types'")
        return original_import(name, globals, locals, fromlist, level)

    sys.modules.pop("assistant.motion_runtime", None)
    monkeypatch.setattr(builtins, "__import__", _import)

    runtime = importlib.import_module("assistant.motion_runtime")

    assert hasattr(runtime, "create_runtime_state")


def test_flat_uploaded_assistant_motion_runtime_imports_without_package_context(
    monkeypatch,
) -> None:
    import importlib
    import sys
    from pathlib import Path

    sys.modules.pop("motion_runtime", None)
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[3] / "src" / "assistant")
    )

    runtime = importlib.import_module("motion_runtime")

    assert hasattr(runtime, "create_runtime_state")


def test_assistant_motion_runtime_reads_yaw_kd_and_hold_speed_eps() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.motion_runtime import create_runtime_state

    old_kd = getattr(runtime_params, "YAW_KD", None)
    old_eps = getattr(runtime_params, "HOLD_SPEED_EPS", None)
    setattr(runtime_params, "YAW_KD", 0.08)
    setattr(runtime_params, "HOLD_SPEED_EPS", 0.25)
    try:
        state = create_runtime_state(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)
    finally:
        if old_kd is None:
            delattr(runtime_params, "YAW_KD")
        else:
            setattr(runtime_params, "YAW_KD", old_kd)
        if old_eps is None:
            delattr(runtime_params, "HOLD_SPEED_EPS")
        else:
            setattr(runtime_params, "HOLD_SPEED_EPS", old_eps)

    assert state.yaw_kd == 0.08
    assert state.hold_speed_eps == 0.25


def test_assistant_motion_runtime_starts_without_fixed_tick_fallback() -> None:
    from assistant.motion_runtime import create_runtime_state

    state = create_runtime_state(timeout_ms=50)

    assert state.tick_ms == 5
    assert state.tick_s == 0.0


def test_assistant_motion_runtime_logs_loaded_ident_lookup_summary(monkeypatch) -> None:
    import assistant.motion_runtime as runtime

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

    runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)

    assert (
        "ident_lookup_loaded",
        {
            "path": runtime.config.IDENT_RESULTS_FILE,
            "wheel_ident": {
                "m": ident_lookup["m"],
                "l": ident_lookup["l"],
                "r": ident_lookup["r"],
            },
        },
    ) in captured


def test_assistant_motion_runtime_ident_lookup_summary_ignores_extra_wheels(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

    captured = []
    ident_lookup = {
        "m": (0.00055, 0.01),
        "l": (0.000581, 0.01),
        "r": (0.000551, 0.01),
        "x": (9.9, 9.9),
    }

    monkeypatch.setattr(runtime, "_load_ident_lookup", lambda path: dict(ident_lookup))
    monkeypatch.setattr(runtime, "_load_gyro_offsets", lambda path: (0.0,) * 6)
    monkeypatch.setattr(
        runtime,
        "_debug_print",
        lambda stage, **payload: captured.append((stage, dict(payload))),
    )

    runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)

    assert (
        "ident_lookup_loaded",
        {
            "path": runtime.config.IDENT_RESULTS_FILE,
            "wheel_ident": {
                "m": ident_lookup["m"],
                "l": ident_lookup["l"],
                "r": ident_lookup["r"],
            },
        },
    ) in captured


def test_assistant_motion_runtime_logs_loaded_gyro_offsets_summary(monkeypatch) -> None:
    import assistant.motion_runtime as runtime

    captured = []
    gyro_offsets = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)

    monkeypatch.setattr(runtime, "_load_ident_lookup", lambda path: {})
    monkeypatch.setattr(runtime, "_load_gyro_offsets", lambda path: gyro_offsets)
    monkeypatch.setattr(
        runtime,
        "_debug_print",
        lambda stage, **payload: captured.append((stage, dict(payload))),
    )

    runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)

    assert (
        "gyro_offsets_loaded",
        {
            "path": runtime.config.GYRO_OFFSET_FILE,
            "gyro_offsets": gyro_offsets,
        },
    ) in captured


def test_assistant_motion_runtime_first_cycle_does_not_fallback_to_fixed_tick_for_speed_loop(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

    class FakeMotor:
        def __init__(self) -> None:
            self.last_duty = 0

        def set_duty(self, duty) -> None:
            self.last_duty = int(duty)

        def stop(self) -> None:
            self.last_duty = 0

    motors = {name: FakeMotor() for name in ("m", "l", "r")}
    state = runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)
    state.hw_bundle = {"motors": motors}
    state.follow_active = True
    captured = []

    monkeypatch.setattr(runtime, "resolve_follow_velocity", lambda state: (0.2, 0.1))
    monkeypatch.setattr(runtime, "compute_heading_correction", lambda state: 0.0)
    monkeypatch.setattr(
        runtime,
        "apply_wheel_speed_control",
        lambda state, wheel_targets, limit, motors=None: captured.append(
            (float(state.tick_s), dict(wheel_targets))
        ),
    )

    runtime.run_base_cycle(state, now_ms=0, cycle_token=object(), hw_bundle=None)

    assert state.tick_s == 0.0
    assert captured == []
    assert state.motor_duties == {"m": 0, "l": 0, "r": 0}
    assert {name: motor.last_duty for name, motor in motors.items()} == {
        "m": 0,
        "l": 0,
        "r": 0,
    }


def test_assistant_motion_runtime_zero_dt_does_not_advance_wheel_filters(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

    calls = []

    def _fake_update_wheel_speeds(filter_bank, raw_ticks, wheel_names):
        calls.append((dict(raw_ticks), tuple(wheel_names)))
        return {name: 0.0 for name in wheel_names}

    state = runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)
    state.follow_active = True

    monkeypatch.setattr(runtime, "resolve_follow_velocity", lambda state: (0.2, 0.1))
    monkeypatch.setattr(runtime, "compute_heading_correction", lambda state: 0.0)
    monkeypatch.setattr(runtime, "update_wheel_speeds", _fake_update_wheel_speeds)

    runtime.run_base_cycle(state, now_ms=0, cycle_token=object(), hw_bundle=None)

    assert state.tick_s == 0.0
    assert calls == [({"m": 0.0, "l": 0.0, "r": 0.0}, ())]


def test_assistant_motion_runtime_zero_dt_keeps_heading_chain_static(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

    captured = []
    state = runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)
    state.follow_active = True
    state.yaw_rate_deg_s = 6.5
    state.gyro_lpf = type(
        "_GyroLpf",
        (),
        {"update": lambda self, value: captured.append(value) or value},
    )()

    monkeypatch.setattr(runtime, "resolve_follow_velocity", lambda state: (0.2, 0.1))
    monkeypatch.setattr(runtime, "compute_heading_correction", lambda state: 0.0)

    runtime.run_base_cycle(state, now_ms=0, cycle_token=object(), hw_bundle=None)

    assert state.tick_s == 0.0
    assert state.yaw_rate_deg_s == 6.5
    assert captured == []


def test_assistant_motion_runtime_zero_dt_keeps_velocity_command_static(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

    state = runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)
    state.follow_active = True
    state.velocity_command = (0.0, 0.0, 0.0)

    monkeypatch.setattr(runtime, "resolve_follow_velocity", lambda state: (0.2, 0.1))
    monkeypatch.setattr(runtime, "compute_heading_correction", lambda state: 0.4)

    runtime.run_base_cycle(state, now_ms=0, cycle_token=object(), hw_bundle=None)

    assert state.tick_s == 0.0
    assert state.velocity_command == (0.0, 0.0, 0.0)


def test_assistant_motion_runtime_idle_zero_dt_skips_heading_hold_correction(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

    state = runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)
    state.follow_active = False
    state.velocity_command = (0.0, 0.0, 0.0)

    monkeypatch.setattr(
        runtime,
        "compute_heading_correction",
        lambda state: (_ for _ in ()).throw(AssertionError("不应进入保持链")),
    )

    result = runtime.run_base_cycle(
        state, now_ms=0, cycle_token=object(), hw_bundle=None
    )

    assert result == "ACK"
    assert state.tick_s == 0.0
    assert state.velocity_command == (0.0, 0.0, 0.0)


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
            "f=1,s=7,v=1,x=0.10,y=-0.05",
            now_ms=1,
        )
        == "BUSY"
    )
    assert state.follow_active is True
    assert state.last_seq == 7
    assert state.state_label == "BUSY"
    assert state.velocity_command == (0.0, 0.0, 0.0)
    assert state.timeout is False


def test_motion_runtime_discards_duplicate_or_older_follow_packet() -> None:
    state = _new_state(timeout_ms=100)

    _apply_line(state, "f=1,s=7,v=1,x=0.10,y=0.00", now_ms=1)

    result = _apply_line(state, "f=1,s=7,v=1,x=0.20,y=0.10", now_ms=2)

    assert result == "IGNORED"
    assert state.last_seq == 7


def test_motion_runtime_marks_follow_inactive_when_target_missing() -> None:
    state = _new_state(timeout_ms=100)

    result = _apply_line(state, "f=1,s=8,v=0,x=0.00,y=0.00", now_ms=2)

    assert result == "HOLD"
    assert state.follow_active is False
    assert state.state_label == "IDLE"
    assert state.velocity_command == (0.0, 0.0, 0.0)
    assert _tick(state, now_ms=3) == "ACK"


def test_motion_runtime_stops_when_timeout_expires() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)

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
    assert state.velocity_command == (0.0, 0.0, 0.0)
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
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "HOLD", now_ms=151)

    assert result == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_newer_follow_can_exit_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "f=1,s=9,v=1,x=0.1,y=-0.1", now_ms=151)

    assert result == "BUSY"
    assert state.state_label == "BUSY"
    assert state.timeout is False
    assert state.last_error == ""
    assert state.last_seq == 9


def test_motion_runtime_reset_odom_clears_timeout_but_keeps_last_seq() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "RESET_ODOM", now_ms=151)

    assert result == "ACK"
    assert state.state_label == "IDLE"
    assert state.timeout is False
    assert state.last_error == ""
    assert state.last_seq == 8


def test_motion_runtime_stop_does_not_clear_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "STOP", now_ms=151)

    assert result == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_disarm_does_not_clear_timeout_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    result = _apply_line(state, "DISARM", now_ms=151)

    assert result == "ACK"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_ping_and_state_query_keep_current_state() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
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
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"
    assert _apply_line(state, "STOP", now_ms=151) == "DONE"

    tick_result = _tick(state, now_ms=152)

    assert tick_result == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True
    assert state.last_error == "timeout_stop"


def test_motion_runtime_velocity_entry_refreshes_timeout_window() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)

    assert _apply_line(state, "VEL 0.1 0.2 0.3", now_ms=80) == "BUSY"
    assert _tick(state, now_ms=110) == "BUSY"
    assert state.state_label == "BUSY"
    assert state.timeout is False


def test_motion_runtime_ignored_legacy_move_does_not_delay_timeout() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)

    assert _apply_line(state, "MOVE 0.1 0.2 15", now_ms=80) == "ERR"
    assert _tick(state, now_ms=110) == "DONE"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True


def test_motion_runtime_reset_odom_clears_velocity_command_but_keeps_last_seq() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=-0.1", now_ms=10)

    result = _apply_line(state, "RESET_ODOM", now_ms=11)

    assert result == "ACK"
    assert state.state_label == "IDLE"
    assert state.velocity_command == (0.0, 0.0, 0.0)
    assert state.last_seq == 8


def test_motion_runtime_hold_does_not_retrigger_timeout_on_later_tick() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)
    assert _tick(state, now_ms=150) == "DONE"

    assert _apply_line(state, "HOLD", now_ms=151) == "DONE"
    assert _tick(state, now_ms=260) == "ACK"
    assert state.state_label == "TIMEOUT"
    assert state.timeout is True


def test_motion_runtime_reset_odom_does_not_start_new_timeout_window() -> None:
    state = _new_state(timeout_ms=100)
    _apply_line(state, "f=1,s=8,v=1,x=0.2,y=0.0", now_ms=10)

    assert _apply_line(state, "RESET_ODOM", now_ms=20) == "ACK"
    assert _tick(state, now_ms=130) == "ACK"
    assert state.state_label == "IDLE"
    assert state.timeout is False


def test_motion_runtime_repeated_hold_does_not_refresh_heading_target() -> None:
    state = _new_state(timeout_ms=100)
    state.follow_active = True
    state.heading_deg = 12.0
    state.target_heading_deg = 12.0
    state.heading_target_ready = True

    assert _apply_line(state, "HOLD", now_ms=20) == "DONE"
    assert state.target_heading_deg == 12.0

    state.heading_deg = 37.0

    assert _apply_line(state, "HOLD", now_ms=21) == "DONE"
    assert state.target_heading_deg == 12.0


def test_motion_runtime_vel_command_keeps_heading_hold_enabled_by_default() -> None:
    class FakeHeading:
        def heading_deg(self):
            return 15.0

    state = _new_state(timeout_ms=100, hw_bundle={"imu": FakeHeading()})

    result = _apply_line(state, "VEL 0.1 0.0 0.0", now_ms=0)

    assert result == "BUSY"
    assert state.velocity_command == (0.0, 0.0, 0.0)
    assert state.target_heading_deg == 15.0


def test_motion_runtime_small_manual_omega_falls_back_to_heading_hold(
    monkeypatch,
) -> None:
    import pytest

    state = _new_state(timeout_ms=100)
    state.heading_deg = 27.0
    state.target_heading_deg = 12.0
    state.heading_target_ready = True
    state.yaw_integral = 0.0
    state.yaw_kp = 0.16
    state.yaw_ki = 0.1
    state.yaw_kd = 0.0
    state.hold_speed_eps = 0.25

    monkeypatch.setitem(
        apply_runtime_command.__globals__,
        "update_heading_from_gyro",
        lambda state, heading_override=None: (
            setattr(state, "tick_s", 0.005),
            setattr(state, "heading_deg", 27.0),
            setattr(state, "yaw_rate_deg_s", 0.0),
        )[-1],
    )

    result = _apply_line(state, "VEL 0.0 0.0 0.1", now_ms=1)

    assert result == "BUSY"
    assert state.velocity_command == pytest.approx((0.0, 0.0, -2.4075))
    assert state.target_heading_deg == 12.0


def test_motion_runtime_passes_dynamic_tick_to_speed_loop(monkeypatch) -> None:
    import pytest

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

    state = _new_state(
        timeout_ms=100,
        hw_bundle={
            "imu": object(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        },
    )
    controllers = {name: FakeController() for name in ("m", "l", "r")}
    state.wheel_controllers = controllers
    state.target_heading_deg = 30.0
    state.heading_target_ready = True
    state.follow_active = True
    state.follow_target_world = (0.0, 0.0)

    monkeypatch.setitem(
        run_base_cycle.__globals__,
        "update_heading_from_gyro",
        lambda state, heading_override=None: (
            setattr(state, "tick_s", 0.012345),
            setattr(state, "heading_deg", 0.0),
            setattr(state, "yaw_rate_deg_s", 0.0),
        )[-1],
    )

    _tick(state, now_ms=10, cycle_token=object())

    assert state.tick_s == pytest.approx(0.012345)
    for controller in controllers.values():
        assert controller.dt_values == [pytest.approx(0.012345)]


def test_motion_runtime_passes_dynamic_tick_to_wheel_filters(monkeypatch) -> None:
    import assistant.motion_runtime as runtime

    class FakeEncoder:
        def __init__(self, values) -> None:
            self.values = list(values)
            self.index = 0

        def read_and_clear(self):
            value = self.values[min(self.index, len(self.values) - 1)]
            self.index += 1
            return value

    dt_values = iter((0.007, 0.013))
    state = _new_state(
        timeout_ms=100,
        hw_bundle={
            "imu": object(),
            "encoders": {name: FakeEncoder((10.0, 20.0)) for name in ("m", "l", "r")},
        },
    )

    monkeypatch.setitem(
        run_base_cycle.__globals__,
        "update_heading_from_gyro",
        lambda state, heading_override=None: (
            setattr(state, "tick_s", next(dt_values)),
            setattr(state, "heading_deg", 0.0),
            setattr(state, "yaw_rate_deg_s", 0.0),
        )[-1],
    )

    _tick(state, now_ms=7, cycle_token=object())
    _tick(state, now_ms=20, cycle_token=object())

    assert state.wheel_filters["m"].reg.long_values == [(7.0, 10.0), (20.0, 15.0)]


def test_motion_runtime_maps_right_shift_direction_to_three_wheel_signs(
    monkeypatch,
) -> None:
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

    monkeypatch.setitem(
        apply_runtime_command.__globals__,
        "update_heading_from_gyro",
        lambda state, heading_override=None: (
            setattr(state, "tick_s", 0.005),
            setattr(state, "heading_deg", 0.0),
            setattr(state, "yaw_rate_deg_s", 0.0),
        )[-1],
    )

    def _fake_apply_wheel_speed_control(state, wheel_targets, limit, motors=None):
        for name in ("m", "l", "r"):
            duty = int(wheel_targets[name] * 1000)
            state.target_wheel_speeds[name] = float(wheel_targets[name])
            state.motor_duties[name] = duty
            if motors is not None:
                motors[name].set_duty(duty)

    monkeypatch.setitem(
        apply_runtime_command.__globals__,
        "apply_wheel_speed_control",
        _fake_apply_wheel_speed_control,
    )

    _apply_line(state, "f=1,s=1,v=1,x=300.0,y=0.0", now_ms=5)
    right_shift = {name: motor.last_duty for name, motor in motors.items()}

    _apply_line(state, "f=1,s=2,v=1,x=0.0,y=300.0", now_ms=1)
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
        "f=1,s=1,v=1,x=0.1,y=0.0",
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
            "f=1,s=1,v=1,x=0.0,y=1.5",
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
        "f=1,s=1,v=1,x=0.1,y=0.0",
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
        "f=1,s=1,v=1,x=0.1,y=0.0",
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
        "f=1,s=1,v=1,x=1.0,y=0.0",
        now_ms=0,
        cycle_token=object(),
    )
    first_command = state.velocity_command

    _tick(state, now_ms=5, cycle_token=object())

    assert first_command == (0.0, 0.0, 0.0)
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
