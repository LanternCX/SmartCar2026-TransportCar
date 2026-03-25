"""主辅车最小运动协议契约测试.

@file tests/contract/master_assistant/test_motion_protocol.py
"""


def test_master_assistant_motion_protocol_contract() -> None:
    from master.protocol import build_move_command
    from assistant.protocol import parse_command

    command = build_move_command(dx=0.10, dy=0.0, dtheta=15.0)
    parsed = parse_command(command)

    assert parsed.kind == "move"
    assert parsed.dx == 0.10
    assert parsed.dy == 0.0
    assert parsed.dtheta == 15.0


def test_master_assistant_hold_contract() -> None:
    from master.protocol import build_hold_command
    from assistant.protocol import parse_command

    parsed = parse_command(build_hold_command())

    assert parsed.kind == "hold"


def test_assistant_state_reply_keeps_minimal_fields() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.armed = True
    state.busy = True
    state.last_cmd = "move"
    state.odom[0] = 0.1
    state.odom[1] = -0.2
    state.heading_deg = 15.0

    line = render_state(state)

    assert line.startswith("STATE ")
    assert "armed=1" in line
    assert "busy=1" in line
    assert "last_cmd=move" in line
    assert "odom=0.100,-0.200" in line
    assert "heading=15.000" in line
    assert "err=" not in line
