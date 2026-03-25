def test_master_decision_selects_box_target_and_builds_assistant_move() -> None:
    from master.decision import decide_from_observation

    decision = decide_from_observation(
        {
            "target": "cone",
            "candidates": ["cone", "box"],
            "offset_x": 0.25,
            "forward": 0.4,
            "assistant_dx": 0.1,
            "assistant_dy": -0.05,
            "assistant_dtheta": 15.0,
        }
    )

    assert decision.selected_target == "box"
    assert decision.self_target["kind"] == "move"
    assert decision.assistant_command == "MOVE 0.100 -0.050 15.000"


def test_master_decision_falls_back_to_hold_without_target() -> None:
    from master.decision import decide_from_observation

    decision = decide_from_observation({})

    assert decision.selected_target == "idle"
    assert decision.self_target["kind"] == "hold"
    assert decision.assistant_command == "HOLD"
