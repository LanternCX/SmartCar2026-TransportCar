def test_master_app_module_imports() -> None:
    from master.app import MasterApp
    from master.app import MasterRuntimeLoop

    assert MasterApp is not None
    assert MasterRuntimeLoop is not None


def test_master_main_returns_runtime_loop() -> None:
    from master.main import main
    from master.app import MasterRuntimeLoop

    runtime = main()

    assert isinstance(runtime, MasterRuntimeLoop)


def test_master_main_can_load_when_master_is_device_root() -> None:
    from pathlib import Path
    import subprocess

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    result = subprocess.run(
        [
            "python3",
            "main.py",
        ],
        cwd=str(runtime_root),
        env={"PYTHONPATH": ""},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_master_boot_can_load_when_master_is_device_root() -> None:
    from pathlib import Path
    import subprocess

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    result = subprocess.run(
        [
            "python3",
            "boot.py",
        ],
        cwd=str(runtime_root),
        env={"PYTHONPATH": ""},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_master_app_only_drives_assistant_in_current_stage() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
        }
    )

    assert result["self_target"] == {"kind": "hold"}
    assert result["selected_target"] == "follower"
    assert result["assistant_command"] == "follow=1,seq=1,valid=1,dx=12.000,dy=-6.000"
    assert result["phase"] == "TRACKING"
    assert result["active_uart"] == "uart6"


def test_master_app_enters_center_hold_for_small_error() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=10,valid=1,target=follower,err_x=3,err_y=-4",
        }
    )

    assert result["self_target"] == {"kind": "hold"}
    assert result["selected_target"] == "follower"
    assert result["assistant_command"] == "follow=1,seq=1,valid=0,dx=0.000,dy=0.000"
    assert result["phase"] == "CENTER_HOLD"


def test_master_app_routes_current_selected_target_before_state_machine() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=11,valid=1,target=follower,err_x=9,err_y=0",
        }
    )

    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["assistant_command"] == "follow=1,seq=1,valid=1,dx=9.000,dy=0.000"


def test_master_app_zeroes_command_when_selected_report_is_expired() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"uart": "uart6", "now_ms": 1200})

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "idle"
    assert result["phase"] == "MARKER_MISSING"
    assert result["self_target"] == {"kind": "hold"}


def test_master_app_uses_selected_target_instead_of_last_arrival() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=8,valid=1,target=follower,err_x=1,err_y=1",
            "now_ms": 1010,
        }
    )

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "CENTER_HOLD"
    assert result["active_uart"] == "uart8"


def test_master_app_zeroes_command_when_step_receives_no_new_input() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"now_ms": 1100})

    assert result["assistant_command"] == "follow=1,seq=2,valid=1,dx=12.000,dy=-6.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["self_target"] == {"kind": "hold"}
    assert result["assistant_state"] == {
        "phase": "TRACKING",
        "selected_target": "follower",
        "target_valid": 1,
        "target_fresh": 1,
    }


def test_master_app_keeps_fresh_target_when_same_uart_frame_is_empty() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"uart": "uart6", "now_ms": 1100})

    assert result["assistant_command"] == "follow=1,seq=2,valid=1,dx=12.000,dy=-6.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["self_target"] == {"kind": "hold"}
    assert result["assistant_state"] == {
        "phase": "TRACKING",
        "selected_target": "follower",
        "target_valid": 1,
        "target_fresh": 1,
    }


def test_master_app_zeroes_command_after_selected_target_leaves_freshness_window() -> (
    None
):
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"now_ms": 1200})

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "idle"
    assert result["phase"] == "MARKER_MISSING"
    assert result["self_target"] == {"kind": "hold"}


def test_master_app_keeps_center_hold_while_target_is_still_fresh() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=10,valid=1,target=follower,err_x=3,err_y=-4",
            "now_ms": 1000,
        }
    )

    result = app.step({"now_ms": 1100})

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "CENTER_HOLD"
    assert result["assistant_state"] == {
        "phase": "CENTER_HOLD",
        "selected_target": "follower",
        "target_valid": 1,
        "target_fresh": 1,
    }


def test_master_app_falls_back_to_configured_uart_when_no_input_arrives() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    result = app.step(None)

    assert result["active_uart"] == "uart6"


def test_master_app_prefers_current_valid_target_over_newer_invalid_report() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=4,valid=1,target=follower,err_x=12,err_y=-6",
        }
    )

    result = app.step(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=5,valid=0,target=follower",
        }
    )

    assert result["assistant_command"] == "follow=1,seq=2,valid=1,dx=12.000,dy=-6.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["active_uart"] == "uart6"
