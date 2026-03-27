def test_master_app_module_imports() -> None:
    from master.app import MasterApp

    assert MasterApp is not None


def test_master_app_runs_single_step_pipeline() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=101,valid=1,target=follower,err_x=0.05,err_y=0.12",
        }
    )

    assert (
        result["assistant_command"]
        == "follow=1,seq=1,valid=1,dx=0.050,dy=0.120,d_angle=0.000"
    )
    assert result["self_target"]["kind"] == "hold"
    assert result["active_uart"] == "uart6"


def test_master_app_keeps_last_command_when_reserved_route_reports() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    first = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=101,valid=1,target=follower,err_x=0.05,err_y=0.12",
        }
    )
    second = app.step(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=1,valid=1,target=follower,err_x=0.90,err_y=0.90",
        }
    )

    assert second["assistant_command"] == first["assistant_command"]
    assert second["phase"] == "follow_track"


def test_master_app_ignores_duplicate_or_invalid_active_report() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    first = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=101,valid=1,target=follower,err_x=0.05,err_y=0.12",
        }
    )
    duplicate = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=101,valid=1,target=follower,err_x=0.50,err_y=0.50",
        }
    )
    invalid = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=bad,valid=1,target=follower,err_x=0.20,err_y=0.20",
        }
    )

    assert duplicate["assistant_command"] == first["assistant_command"]
    assert invalid["assistant_command"] == first["assistant_command"]
