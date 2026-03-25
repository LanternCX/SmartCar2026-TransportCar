def test_master_stability_baseline_keeps_attitude_and_kinematics_contract() -> None:
    from master.stability.kinematics import body_axis_semantics
    from master.stability.attitude import euler_to_quaternion, quaternion_to_euler

    semantics = body_axis_semantics()

    assert semantics["x_positive"] == "right"
    assert semantics["y_positive"] == "forward"
    quat = euler_to_quaternion(0.0, 0.0, 10.0)
    yaw_deg = quaternion_to_euler(quat)[2]
    assert abs(yaw_deg - 10.0) < 1e-3


def test_master_stability_baseline_keeps_filter_chain_contract() -> None:
    from master.stability.filtering import build_speed_filter_chain

    chain = build_speed_filter_chain()
    filtered = chain.update(0.0)
    filtered = chain.update(100.0)

    assert filtered == 5.0
