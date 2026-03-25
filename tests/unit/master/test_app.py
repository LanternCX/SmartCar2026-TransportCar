def test_master_app_module_imports() -> None:
    from master.app import MasterApp

    assert MasterApp is not None


def test_master_app_runs_single_step_pipeline() -> None:
    from master.app import MasterApp

    app = MasterApp(vision_uart="uart6", camera_ids=("cam_a", "cam_b"))

    result = app.step(
        observation={
            "target": "box",
            "offset_x": 0.1,
            "forward": 0.25,
            "assistant_dx": 0.05,
            "assistant_dy": 0.0,
            "assistant_dtheta": 10.0,
        }
    )

    assert result["assistant_command"] == "MOVE 0.050 0.000 10.000"
    assert result["self_target"]["kind"] == "move"
