"""主辅车跟随协议契约测试.

@file tests/contract/master_assistant/test_motion_protocol.py
"""


def test_master_assistant_motion_protocol_contract() -> None:
    from master.protocol import build_follow_command
    from assistant.protocol import parse_command

    command = build_follow_command(seq=7, valid=1, dx=0.10, dy=0.0)
    parsed = parse_command(command)

    assert parsed.kind == "follow"
    assert parsed.seq == 7
    assert parsed.valid == 1
    assert parsed.dx == 0.10
    assert parsed.dy == 0.0
    assert command == "follow=1,seq=7,valid=1,dx=0.100,dy=0.000"


def test_master_assistant_invalid_target_contract() -> None:
    from master.protocol import build_follow_command
    from assistant.protocol import parse_command

    parsed = parse_command(build_follow_command(seq=8, valid=0, dx=0.0, dy=0.0))

    assert parsed.kind == "follow"
    assert parsed.valid == 0
    assert parsed.dx == 0.0
    assert parsed.dy == 0.0


def test_assistant_state_reply_keeps_minimal_status_payload() -> None:
    from assistant.state import AssistantState
    from assistant.status import render_state
    from master.protocol import parse_assistant_state

    state = AssistantState()
    state.follow_active = True
    state.last_seq = 7
    state.timeout = False

    line = render_state(state)

    assert (
        line == "state=1,state_label=BUSY,last_seq=7,follow_active=1,"
        "heading_deg=0.000,target_heading_deg=0.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.0000,odom_y=0.0000,base_ok=0"
    )
    payload = parse_assistant_state(line)

    assert payload is not None
    assert sorted(payload.keys()) == [
        "base_ok",
        "follow_active",
        "heading_deg",
        "last_seq",
        "odom_x",
        "odom_y",
        "state_label",
        "target_heading_deg",
        "yaw_rate_deg_s",
    ]
