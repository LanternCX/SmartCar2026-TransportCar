def test_assistant_protocol_parses_move_command() -> None:
    from assistant.protocol import parse_command

    result = parse_command("MOVE 0.10 -0.05 15")

    assert result.kind == "move"
    assert result.dx == 0.10
    assert result.dy == -0.05
    assert result.dtheta == 15.0


def test_assistant_protocol_parses_control_commands() -> None:
    from assistant.protocol import parse_command

    assert parse_command("ARM").kind == "arm"
    assert parse_command("STATE?").kind == "state_query"
    assert parse_command("RESET_ODOM").kind == "reset_odom"
