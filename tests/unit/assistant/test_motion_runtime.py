def test_motion_runtime_executes_arm_move_and_stop() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)

    assert runtime.apply_command(parse_command("ARM"), now_ms=0) == "ACK"
    assert (
        runtime.apply_command(parse_command("MOVE 0.10 -0.05 15"), now_ms=1) == "BUSY"
    )
    assert runtime.state.busy is True
    assert runtime.state.last_cmd == "move"

    runtime.apply_command(parse_command("STOP"), now_ms=2)

    assert runtime.state.busy is False
    assert runtime.state.velocity_command == (0.0, 0.0, 0.0)


def test_motion_runtime_stops_when_timeout_expires() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    runtime.apply_command(parse_command("ARM"), now_ms=0)
    runtime.apply_command(parse_command("VEL 0.2 0.0 5"), now_ms=10)

    assert runtime.tick(now_ms=150) == "DONE"
    assert runtime.state.busy is False
    assert runtime.state.last_error == "timeout_stop"
