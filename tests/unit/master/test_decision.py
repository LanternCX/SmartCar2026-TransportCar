import pytest


def _assert_follow_command_semantics(command, seq, valid, x, y) -> None:
    from assistant.protocol import parse_command

    parsed = parse_command(command)

    assert parsed.kind == "follow"
    assert parsed.seq == seq
    assert parsed.valid == valid
    assert parsed.dx == x
    assert parsed.dy == y


def test_decision_align_x_outputs_only_lateral_follow_command() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation(
        {
            "control_seq": 4,
            "selected_target": "tracked",
            "valid": 1,
            "phase": "ALIGN_X",
            "err_x": 0.1,
            "err_y": -0.05,
        }
    )

    assert decision.selected_target == "tracked"
    assert decision.phase == "ALIGN_X"
    assert decision.self_target == {"kind": "hold"}
    assert decision.assistant_target["valid"] == 1
    assert decision.assistant_target["dx"] == pytest.approx(0.01)
    assert decision.assistant_target["dy"] == pytest.approx(0.0)
    _assert_follow_command_semantics(decision.assistant_command, 4, 1, 0.01, 0.0)


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


def test_decision_align_y_outputs_only_longitudinal_follow_command() -> None:
    from master.vision.decision import decide_from_observation

    decision = decide_from_observation(
        {
            "control_seq": 7,
            "selected_target": "tracked",
            "valid": 1,
            "fresh": 1,
            "has_new_input": 0,
            "phase": "ALIGN_Y",
            "err_x": 12.0,
            "err_y": -6.0,
        }
    )

    assert decision.phase == "ALIGN_Y"
    assert decision.selected_target == "tracked"
    assert decision.assistant_target["valid"] == 1
    assert decision.assistant_target["dx"] == pytest.approx(0.0)
    assert decision.assistant_target["dy"] == pytest.approx(-0.6)
    _assert_follow_command_semantics(decision.assistant_command, 7, 1, 0.0, -0.6)
    assert decision.assistant_state == {
        "phase": "ALIGN_Y",
        "selected_target": "tracked",
        "target_valid": 1,
        "target_fresh": 1,
    }
