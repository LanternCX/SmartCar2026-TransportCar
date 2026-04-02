def test_assistant_follow_offset_rotation_belongs_to_control_math() -> None:
    from assistant.ctrl.kinematics import rotate_body_delta_to_world

    world_x, world_y = rotate_body_delta_to_world(10.0, 0.0, 90.0)

    assert abs(world_x) < 1e-6
    assert abs(world_y + 10.0) < 1e-6
