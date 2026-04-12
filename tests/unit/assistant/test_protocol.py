def test_assistant_protocol_parses_follow_command() -> None:
    from assistant.protocol import parse_command

    result = parse_command("f=1,s=7,v=1,x=0.10,y=-0.05")

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
        parse_command("f=1,s=7,x=0.10,y=-0.05")


def test_assistant_protocol_parses_velocity_mode_without_seq() -> None:
    from assistant.protocol import parse_command

    result = parse_command("f=1,m=1,x=0.10,y=-0.05")

    assert result.kind == "follow_velocity"
    assert result.seq == 0
    assert result.vx == 0.1
    assert result.vy == -0.05


def test_assistant_protocol_parses_key_value_follow_without_mode_field() -> None:
    from assistant.protocol import parse_command

    result = parse_command("f=1,s=7,v=1,x=0.10,y=-0.05")

    assert result.kind == "follow"
    assert result.seq == 7
    assert result.valid == 1
    assert result.dx == 0.1
    assert result.dy == -0.05


def test_assistant_protocol_rejects_removed_legacy_short_csv_follow() -> None:
    import pytest

    from assistant.protocol import parse_command

    with pytest.raises(ValueError, match="unsupported_command"):
        parse_command("F,7,1,0.10,-0.05")
