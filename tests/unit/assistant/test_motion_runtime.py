def test_motion_runtime_accepts_follow_command_and_updates_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    assert (
        runtime.apply_command(
            parse_command("follow=1,seq=7,valid=1,dx=0.10,dy=-0.05,d_angle=15"),
            now_ms=1,
        )
        == "BUSY"
    )
    assert runtime.state.follow_active is True
    assert runtime.state.last_seq == 7
    assert runtime.state.timeout is False


def test_motion_runtime_discards_duplicate_or_older_follow_packet() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    runtime.apply_command(
        parse_command("follow=1,seq=7,valid=1,dx=0.10,dy=0.00,d_angle=0"),
        now_ms=1,
    )

    result = runtime.apply_command(
        parse_command("follow=1,seq=7,valid=1,dx=0.20,dy=0.10,d_angle=0"),
        now_ms=2,
    )

    assert result == "IGNORED"
    assert runtime.state.last_seq == 7


def test_motion_runtime_marks_follow_inactive_when_target_missing() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    result = runtime.apply_command(
        parse_command("follow=1,seq=8,valid=0,dx=0.00,dy=0.00,d_angle=0"),
        now_ms=2,
    )

    assert result == "HOLD"
    assert runtime.state.follow_active is False
    assert runtime.tick(now_ms=3) == "ACK"


def test_motion_runtime_stops_when_timeout_expires() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(
        parse_command("follow=1,seq=8,valid=1,dx=0.2,dy=0.0,d_angle=5"), now_ms=10
    )

    assert runtime.tick(now_ms=150) == "DONE"
    assert runtime.state.follow_active is False
    assert runtime.state.timeout is True
    assert runtime.state.last_error == "timeout_stop"
