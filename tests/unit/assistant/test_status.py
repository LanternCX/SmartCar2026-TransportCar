def test_assistant_state_reply_keeps_minimal_fields() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.follow_active = True
    state.last_seq = 7

    line = render_state(state)

    assert line.startswith("state=1,state_label=BUSY,last_seq=7,follow_active=1,")
    assert "heading_deg=" in line
    assert "target_heading_deg=" in line
    assert "yaw_rate_deg_s=" in line
    assert "odom_x=" in line
    assert "odom_y=" in line
    assert "base_ok=0" in line


def test_assistant_state_contract_keeps_last_seq_and_state_label() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.last_seq = 8
    state.follow_active = False
    state.last_error = "timeout_stop"
    state.timeout = True

    line = render_state(state)

    assert "last_seq=8" in line
    assert "state_label=TIMEOUT" in line


def test_assistant_state_reply_contract_has_required_minimal_fields() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.last_seq = 9
    state.follow_active = True

    line = render_state(state)

    assert line.startswith("state=1,")
    assert "state_label=BUSY" in line
    assert "last_seq=9" in line
    assert "follow_active=1" in line


def test_assistant_state_reply_only_uses_supported_state_labels() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.last_seq = 4
    state.follow_active = False
    state.state_label = "TIMEOUT"

    line = render_state(state)

    assert line.startswith("state=1,state_label=TIMEOUT,last_seq=4,follow_active=0,")
    assert "heading_deg=" in line
    assert "target_heading_deg=" in line
    assert "yaw_rate_deg_s=" in line
    assert "odom_x=" in line
    assert "odom_y=" in line
    assert "base_ok=0" in line
