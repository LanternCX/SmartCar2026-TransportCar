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


def test_master_motion_runtime_reads_yaw_runtime_params() -> None:
    import master.runtime_params as runtime_params
    from master.motion_runtime import MotionRuntime

    old_kp = runtime_params.YAW_KP
    runtime_params.YAW_KP = 0.42
    try:
        runtime = MotionRuntime()
    finally:
        runtime_params.YAW_KP = old_kp

    assert runtime.yaw_kp == 0.42


def test_master_motion_runtime_keeps_heading_hold_enabled_by_default() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()

    assert runtime.heading_hold_enabled is True


def test_master_motion_runtime_heading_hold_output_changes_with_heading_error() -> None:
    from master.motion_runtime import MotionRuntime

    runtime = MotionRuntime()
    runtime.apply_self_target({"kind": "vel", "vx": 0.1, "vy": 0.0, "omega": 0.0})

    output = runtime.update_heading_hold(current_heading_deg=15.0)

    assert output["kind"] == "vel"
    assert output["vx"] == 0.1
    assert output["vy"] == 0.0
    assert output["omega"] != 0.0
