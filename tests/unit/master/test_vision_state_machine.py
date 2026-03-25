def test_master_vision_state_machine_outputs_motion_target() -> None:
    from master.vision_state_machine import VisionStateMachine

    machine = VisionStateMachine()

    target = machine.step(observation={"target": "box"})

    assert target is not None
    assert target["phase"] == "tracking"


def test_master_vision_state_machine_holds_when_target_missing() -> None:
    from master.vision_state_machine import VisionStateMachine

    machine = VisionStateMachine()

    target = machine.step(observation={})

    assert target["phase"] == "search"
    assert target["self"]["kind"] == "hold"


def test_master_vision_state_machine_selects_box_and_outputs_assistant_target() -> None:
    from master.vision_state_machine import VisionStateMachine

    machine = VisionStateMachine()

    target = machine.step(
        observation={
            "target": "cone",
            "candidates": ["cone", "box"],
            "offset_x": 0.1,
            "forward": 0.2,
            "assistant_dx": 0.05,
            "assistant_dy": 0.0,
            "assistant_dtheta": 10.0,
        }
    )

    assert target["selected_target"] == "box"
    assert target["assistant"]["kind"] == "move"
