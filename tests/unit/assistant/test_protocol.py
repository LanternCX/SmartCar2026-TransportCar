def test_assistant_protocol_parses_follow_command() -> None:
    from assistant.protocol import parse_command

    result = parse_command("follow=1,seq=7,valid=1,dx=0.10,dy=-0.05")

    assert result.kind == "follow"
    assert result.seq == 7
    assert result.valid == 1
    assert result.dx == 0.10
    assert result.dy == -0.05


def test_assistant_protocol_parses_control_commands() -> None:
    from assistant.protocol import parse_command

    assert parse_command("ARM").kind == "arm"
    assert parse_command("STATE?").kind == "state_query"
    assert parse_command("RESET_ODOM").kind == "reset_odom"


def test_assistant_protocol_rejects_follow_packet_missing_required_field() -> None:
    import pytest

    from assistant.protocol import parse_command

    with pytest.raises(ValueError, match="missing_required_field"):
        parse_command("follow=1,seq=7,dx=0.10,dy=-0.05")
