def test_assistant_app_module_imports() -> None:
    from assistant.app import AssistantApp
    from assistant.app import AssistantRuntimeLoop

    assert AssistantApp is not None
    assert AssistantRuntimeLoop is not None


def test_assistant_main_returns_runtime_loop() -> None:
    from assistant.main import main
    from assistant.app import AssistantRuntimeLoop

    runtime = main()

    assert isinstance(runtime, AssistantRuntimeLoop)


def test_assistant_main_can_load_when_assistant_is_device_root() -> None:
    from pathlib import Path
    import subprocess

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "assistant"
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


def test_assistant_main_dispatches_calibrate_gyro_when_c9_is_held() -> None:
    from assistant.main import main

    result = main(button_reader=lambda pin: pin == "C9")

    assert result == "calibrate_gyro"


def test_assistant_main_dispatches_runtime_when_no_button_is_held() -> None:
    from assistant.main import main

    runtime = main(button_reader=lambda pin: False)

    assert hasattr(runtime, "step")


def test_assistant_app_handles_ping_and_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    assert app.handle_line("PING", now_ms=0) == "ACK,last_seq=0"
    state = app.handle_line("STATE?", now_ms=1)

    assert state.startswith("state=1,")


def test_assistant_app_maps_auxiliary_entries_to_ack_with_last_seq() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)

    hold_reply = app.handle_line("HOLD", now_ms=11)
    stop_reply = app.handle_line("STOP", now_ms=12)
    reset_reply = app.handle_line("RESET_ODOM", now_ms=13)

    assert hold_reply == "ACK,last_seq=8"
    assert stop_reply == "ACK,last_seq=8"
    assert reset_reply == "ACK,last_seq=8"


def test_assistant_app_keeps_follow_phase_silent_but_reports_timeout() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    follow_reply = app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)
    busy_tick_reply = app.tick(now_ms=50)
    timeout_reply = app.tick(now_ms=120)

    assert follow_reply == ""
    assert busy_tick_reply == ""
    assert timeout_reply == "TIMEOUT,last_seq=8"


def test_assistant_app_reports_timeout_only_once_until_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)

    first_timeout_reply = app.tick(now_ms=120)
    repeated_timeout_reply = app.tick(now_ms=130)
    state_reply = app.handle_line("STATE?", now_ms=131)

    assert first_timeout_reply == "TIMEOUT,last_seq=8"
    assert repeated_timeout_reply == ""
    assert state_reply == "state=1,state_label=TIMEOUT,last_seq=8,follow_active=0"


def test_assistant_app_returns_err_for_malformed_or_unknown_packets() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    malformed_reply = app.handle_line(
        "follow=1,seq=oops,valid=1,dx=0.10,dy=0.00", now_ms=10
    )
    unknown_reply = app.handle_line("WHATEVER", now_ms=11)
    follow_reply = app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=12)

    assert malformed_reply == "ERR"
    assert unknown_reply == "ERR"
    assert follow_reply == ""


def test_assistant_app_accepts_vel_but_still_rejects_move() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    vel_reply = app.handle_line("VEL 0.1 0.2 0.3", now_ms=10)
    move_reply = app.handle_line("MOVE 0.1 0.2 15", now_ms=11)

    assert vel_reply == "ACK,last_seq=0"
    assert move_reply == "ERR"
