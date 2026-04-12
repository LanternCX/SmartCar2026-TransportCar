def test_assistant_state_imports_without_typing_module(monkeypatch) -> None:
    import builtins
    import importlib
    import sys

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "typing":
            raise ImportError("no module named 'typing'")
        return original_import(name, globals, locals, fromlist, level)

    sys.modules.pop("assistant.state", None)
    monkeypatch.setattr(builtins, "__import__", _import)

    state_module = importlib.import_module("assistant.state")

    assert hasattr(state_module, "MotionRuntimeState")


def test_assistant_state_reply_keeps_minimal_fields() -> None:
    from assistant.state import AssistantState
    from assistant.status import render_state

    state = AssistantState()
    state.follow_active = True
    state.last_seq = 7

    line = render_state(state)

    assert (
        line == "state=1,state_label=BUSY,last_seq=7,follow_active=1,"
        "heading_deg=0.000,target_heading_deg=0.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.0000,odom_y=0.0000,base_ok=0"
    )


def test_assistant_state_contract_keeps_last_seq_and_state_label() -> None:
    from assistant.state import AssistantState
    from assistant.status import render_state

    state = AssistantState()
    state.last_seq = 8
    state.follow_active = False
    state.last_error = "timeout_stop"
    state.timeout = True

    line = render_state(state)

    assert (
        line == "state=1,state_label=TIMEOUT,last_seq=8,follow_active=0,"
        "heading_deg=0.000,target_heading_deg=0.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.0000,odom_y=0.0000,base_ok=0"
    )


def test_assistant_state_reply_contract_has_required_minimal_fields() -> None:
    from assistant.state import AssistantState
    from assistant.status import render_state

    state = AssistantState()
    state.last_seq = 9
    state.follow_active = True

    line = render_state(state)

    assert line.startswith("state=1,")
    assert "state_label=BUSY" in line
    assert "last_seq=9" in line
    assert "follow_active=1" in line


def test_assistant_state_reply_only_uses_supported_state_labels() -> None:
    from assistant.state import AssistantState
    from assistant.status import render_state

    state = AssistantState()
    state.last_seq = 4
    state.follow_active = False
    state.state_label = "TIMEOUT"

    line = render_state(state)

    assert (
        line == "state=1,state_label=TIMEOUT,last_seq=4,follow_active=0,"
        "heading_deg=0.000,target_heading_deg=0.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.0000,odom_y=0.0000,base_ok=0"
    )


def test_assistant_state_reply_does_not_write_back_runtime_internal_label() -> None:
    from assistant.state import AssistantState
    from assistant.status import render_state

    state = AssistantState()
    state.state_label = "CONTROL_LOOP"

    line = render_state(state)

    assert "state_label=IDLE" in line
    assert state.state_label == "CONTROL_LOOP"


def test_assistant_state_owner_and_serializer_boundary() -> None:
    from assistant.motion_runtime import create_runtime_state

    state = create_runtime_state(timeout_ms=50)
    state_line = getattr(state, "state_line")

    assert state_line() == (
        "state=1,state_label=IDLE,last_seq=0,follow_active=0,"
        "heading_deg=0.000,target_heading_deg=0.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.0000,odom_y=0.0000,base_ok=0"
    )


def test_assistant_state_module_exposes_runtime_and_control_state() -> None:
    from assistant.state import AssistantControlState, MotionRuntimeState

    state = MotionRuntimeState()
    control_state = AssistantControlState()

    assert type(state).__name__ == "MotionRuntimeState"
    assert hasattr(control_state, "follow_target_world")


def test_assistant_state_module_keeps_runtime_field_annotations() -> None:
    from assistant.state import MotionRuntimeState

    annotations = MotionRuntimeState.__annotations__

    expected_fields = {
        "control",
        "hw_bundle",
        "safety",
        "tick_ms",
        "tick_s",
        "_last_cycle_token",
        "_last_base_snapshot",
        "_last_control_cycle_token",
        "state_line",
    }

    assert expected_fields <= set(annotations)
