def test_master_protocol_follow_builder_rejects_removed_reason_field() -> None:
    import pytest

    from master.protocol import build_follow_command

    with pytest.raises(TypeError):
        build_follow_command(seq=3, valid=0, dx=0.0, dy=0.0, reason="stale")
