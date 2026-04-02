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


def test_assistant_state_owner_and_serializer_boundary() -> None:
    import assistant.ctrl.chassis as chassis_module
    from assistant.motion_runtime import MotionRuntime

    assert not hasattr(chassis_module, "ChassisRuntime"), (
        "控制层不应继续暴露整周期运行时 owner"
    )
    assert not hasattr(chassis_module, "CoreRuntime"), (
        "控制层不应继续暴露长期状态 owner 的别名"
    )

    runtime = MotionRuntime(timeout_ms=50)

    assert runtime.state_line() == (
        "state=1,state_label=IDLE,last_seq=0,follow_active=0,"
        "heading_deg=0.000,target_heading_deg=0.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.0000,odom_y=0.0000,base_ok=0"
    )
