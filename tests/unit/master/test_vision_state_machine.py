def test_state_machine_marks_missing_when_target_is_invalid() -> None:
    from master.vision.state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(valid=0, err_x=3.0, err_y=-4.0)

    assert result["phase"] == "MARKER_MISSING"
    assert result["hold"] is True


def test_state_machine_enters_center_hold_when_error_is_inside_deadzone() -> None:
    from master.vision.state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(valid=1, err_x=3.0, err_y=-4.0)

    assert result["phase"] == "CENTER_HOLD"
    assert result["hold"] is True


def test_state_machine_enters_align_x_when_x_is_outside_deadzone() -> None:
    from master.vision.state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(valid=1, err_x=12.0, err_y=-4.0)

    assert result["phase"] == "ALIGN_X"
    assert result["hold"] is False


def test_state_machine_keeps_current_public_inputs_while_only_returning_phase_state() -> (
    None
):
    from master.vision.state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)
    result = machine.step(
        valid=1,
        err_x=3.0,
        err_y=-12.0,
        has_target=True,
        has_new_input=False,
    )

    assert result["phase"] == "ALIGN_Y"
    assert result["hold"] is False
    assert set(result.keys()) <= {"phase", "hold"}


def test_state_machine_ignores_whether_input_is_new_when_target_is_still_available() -> (
    None
):
    from master.vision.state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(
        has_target=True,
        err_x=3.0,
        err_y=-12.0,
        has_new_input=False,
    )

    assert result["phase"] == "ALIGN_Y"
    assert result["hold"] is False


def test_state_machine_returns_to_align_x_immediately_when_x_drifts_outside_deadzone() -> (
    None
):
    from master.vision.state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    first = machine.step(valid=1, err_x=3.0, err_y=-12.0)
    second = machine.step(valid=1, err_x=9.0, err_y=-12.0)

    assert first["phase"] == "ALIGN_Y"
    assert second["phase"] == "ALIGN_X"
    assert second["hold"] is False
