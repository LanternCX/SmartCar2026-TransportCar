def test_state_machine_marks_missing_when_target_is_invalid() -> None:
    from master.vision_state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(valid=0, err_x=3.0, err_y=-4.0)

    assert result["phase"] == "MARKER_MISSING"
    assert result["hold"] is True


def test_state_machine_enters_center_hold_when_error_is_inside_deadzone() -> None:
    from master.vision_state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(valid=1, err_x=3.0, err_y=-4.0)

    assert result["phase"] == "CENTER_HOLD"
    assert result["hold"] is True


def test_state_machine_tracks_when_error_is_outside_deadzone() -> None:
    from master.vision_state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(valid=1, err_x=12.0, err_y=-4.0)

    assert result["phase"] == "TRACKING"
    assert result["hold"] is False


def test_state_machine_ignores_whether_input_is_new_when_target_is_still_available() -> (
    None
):
    from master.vision_state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(
        has_target=True,
        err_x=12.0,
        err_y=-4.0,
        has_new_input=False,
    )

    assert result["phase"] == "TRACKING"
    assert result["hold"] is False
