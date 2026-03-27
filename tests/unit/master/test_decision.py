def test_master_decision_builds_follow_command_from_vision_error() -> None:
    from master.decision import decide_from_observation

    decision = decide_from_observation(
        {
            "control_seq": 4,
            "camera_id": "cam_a",
            "target": "follower",
            "valid": 1,
            "err_x": 0.1,
            "err_y": -0.05,
        }
    )

    assert decision.selected_target == "follower"
    assert decision.self_target["kind"] == "hold"
    assert decision.assistant_target["valid"] == 1
    assert (
        decision.assistant_command
        == "follow=1,seq=4,valid=1,dx=0.100,dy=-0.050,d_angle=0.000"
    )


def test_master_decision_falls_back_to_invalid_follow_without_target() -> None:
    from master.decision import decide_from_observation

    decision = decide_from_observation({"control_seq": 5})

    assert decision.selected_target == "idle"
    assert decision.self_target["kind"] == "hold"
    assert decision.assistant_target["valid"] == 0
    assert (
        decision.assistant_command
        == "follow=1,seq=5,valid=0,dx=0.000,dy=0.000,d_angle=0.000"
    )
