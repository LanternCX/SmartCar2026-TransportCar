def test_master_motion_runtime_tracks_latest_self_target() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    target = {"kind": "move", "vx": 0.0, "vy": 0.3, "omega": 5.0}

    result = runtime.apply_self_target(target)

    assert result == target
    assert runtime.last_target == target


def test_master_motion_runtime_builds_assistant_command_interface() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    command = runtime.build_assistant_command(dx=0.1, dy=0.0, dtheta=15.0)

    assert command == "MOVE 0.100 0.000 15.000"
