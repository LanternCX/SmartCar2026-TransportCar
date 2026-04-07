def _assert_follow_command_semantics(command, seq, valid, x, y) -> None:
    from assistant.protocol import parse_command

    parsed = parse_command(command)

    assert parsed.kind == "follow"
    assert parsed.seq == seq
    assert parsed.valid == valid
    assert parsed.dx == x
    assert parsed.dy == y


def test_decision_builds_planar_follow_command_from_vision_error() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation(
        {
            "control_seq": 4,
            "selected_target": "tracked",
            "valid": 1,
            "phase": "TRACKING",
            "err_x": 0.1,
            "err_y": -0.05,
        }
    )

    assert decision.selected_target == "tracked"
    assert decision.phase == "TRACKING"
    assert decision.self_target == {"kind": "hold"}
    assert decision.assistant_target == {
        "valid": 1,
        "dx": 0.001,
        "dy": -0.0005,
    }
    _assert_follow_command_semantics(decision.assistant_command, 4, 1, 0.001, -0.001)


def test_decision_outputs_zero_planar_command_when_target_is_invalid() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation(
        {"control_seq": 3, "valid": 0, "source_status": "invalid"}
    )

    assert decision.selected_target == "idle"
    assert decision.self_target == {"kind": "hold"}
    assert decision.assistant_target == {"valid": 0, "dx": 0.0, "dy": 0.0}
    _assert_follow_command_semantics(decision.assistant_command, 3, 0, 0.0, 0.0)


def test_decision_outputs_zero_when_report_is_stale() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation(
        {"control_seq": 4, "valid": 1, "phase": "MARKER_MISSING", "stale": 1}
    )

    assert decision.phase == "MARKER_MISSING"
    assert decision.assistant_target == {"valid": 0, "dx": 0.0, "dy": 0.0}
    _assert_follow_command_semantics(decision.assistant_command, 4, 0, 0.0, 0.0)


def test_decision_holds_inside_center_deadzone() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation(
        {
            "control_seq": 6,
            "valid": 1,
            "phase": "CENTER_HOLD",
            "err_x": 2.0,
            "err_y": -1.0,
        }
    )

    assert decision.phase == "CENTER_HOLD"
    assert decision.assistant_target == {"valid": 0, "dx": 0.0, "dy": 0.0}
    _assert_follow_command_semantics(decision.assistant_command, 6, 0, 0.0, 0.0)


def test_decision_keeps_tracking_with_fresh_target_without_new_input() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation(
        {
            "control_seq": 7,
            "selected_target": "tracked",
            "valid": 1,
            "fresh": 1,
            "has_new_input": 0,
            "phase": "TRACKING",
            "err_x": 12.0,
            "err_y": -6.0,
        }
    )

    assert decision.phase == "TRACKING"
    assert decision.selected_target == "tracked"
    assert decision.assistant_target == {
        "valid": 1,
        "dx": 0.12,
        "dy": -0.06,
    }
    _assert_follow_command_semantics(decision.assistant_command, 7, 1, 0.12, -0.06)
    assert decision.assistant_state == {
        "phase": "TRACKING",
        "selected_target": "tracked",
        "target_valid": 1,
        "target_fresh": 1,
    }
