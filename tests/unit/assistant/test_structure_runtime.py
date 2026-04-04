def test_assistant_hw_bundle_uses_confirmed_mapping() -> None:
    from assistant.app import build_hw_bundle

    hw_bundle = build_hw_bundle()
    encoder_pins = {
        name: (port.phase_a_pin, port.phase_b_pin, port.invert)
        for name, port in hw_bundle["encoders"].items()
    }

    assert hw_bundle["uart"]["uart3"].uart_id == 2
    assert hw_bundle["motors"]["m"].port_name == "PWM_C30_DIR_C31"
    assert hw_bundle["motors"]["l"].port_name == "PWM_D4_DIR_D5"
    assert hw_bundle["motors"]["r"].port_name == "PWM_D6_DIR_D7"
    assert encoder_pins == {
        "m": ("D15", "D16", True),
        "l": ("C0", "C1", True),
        "r": ("C2", "C3", True),
    }


def test_assistant_runtime_process_entry_drives_one_cycle() -> None:
    import assistant.motion_runtime as runtime

    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    hw_bundle = {
        "imu": FakeHeading(),
        "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
    }

    create_runtime_state = getattr(runtime, "create_runtime_state")
    run_base_cycle = getattr(runtime, "run_base_cycle")
    state = create_runtime_state(timeout_ms=100, hw_bundle=hw_bundle)
    reply = run_base_cycle(
        state,
        hw_bundle=hw_bundle,
        now_ms=0,
        cycle_token=object(),
    )

    assert isinstance(reply, str)
    assert bool(state.base_ok) is True
    assert tuple(state.odom) == (0.0, 0.0)
    assert state.heading_deg == 0.0


def test_assistant_runtime_process_entry_applies_follow_command() -> None:
    import assistant.motion_runtime as runtime
    from assistant.protocol import Command

    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    class FakeMotor:
        def __init__(self) -> None:
            self.last_duty = 0

        def set_duty(self, duty) -> None:
            self.last_duty = int(duty)

        def stop(self) -> None:
            self.last_duty = 0

    hw_bundle = {
        "imu": FakeHeading(),
        "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        "motors": {name: FakeMotor() for name in ("m", "l", "r")},
    }

    state = runtime.create_runtime_state(timeout_ms=100, hw_bundle=hw_bundle)
    reply = runtime.apply_runtime_command(
        state,
        Command(kind="follow", seq=8, valid=1, dx=0.10, dy=0.0),
        now_ms=10,
        cycle_token=object(),
    )

    assert reply == "BUSY"
    assert state.last_seq == 8
    assert bool(state.follow_active) is True
    assert state.state_label == "BUSY"


def test_assistant_control_state_is_kept_under_state_module() -> None:
    from assistant.state import AssistantControlState, AssistantState

    state = AssistantState()
    control_state = AssistantControlState()

    assert hasattr(state, "follow_active")
    assert hasattr(control_state, "follow_target_world")


def test_assistant_chassis_shell_module_is_removed() -> None:
    import importlib

    import pytest

    import assistant.app as runtime_app

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("assistant.ctrl.chassis")

    assert hasattr(runtime_app, "AssistantApp")


def test_assistant_runtime_state_keeps_minimal_public_fields() -> None:
    import assistant.motion_runtime as runtime

    state = runtime.create_runtime_state(timeout_ms=100)

    assert type(state).__name__ == "MotionRuntimeState"
    assert hasattr(state, "follow_active")
    assert hasattr(state, "last_seq")
    assert hasattr(state, "odom")
    assert hasattr(state, "heading_deg")
    assert hasattr(state, "state") is False


def test_assistant_state_module_does_not_hold_runtime_flow_methods() -> None:
    from assistant.state import MotionRuntimeState

    assert hasattr(MotionRuntimeState, "tick") is False
    assert hasattr(MotionRuntimeState, "apply_command") is False
    assert hasattr(MotionRuntimeState, "state_line") is False
