def test_master_motion_runtime_tracks_latest_self_target() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    target = {"kind": "hold"}

    result = runtime.apply_self_target(target)

    assert result == target
    assert runtime.last_target == target


def test_master_motion_runtime_allocates_monotonic_follow_sequence() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    assert runtime.next_control_seq() == 1
    assert runtime.next_control_seq() == 2
