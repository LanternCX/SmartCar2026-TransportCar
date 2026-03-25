def test_assistant_app_module_imports() -> None:
    from assistant.app import AssistantApp

    assert AssistantApp is not None


def test_assistant_app_handles_ping_and_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    assert app.handle_line("PING", now_ms=0) == "ACK"
    state = app.handle_line("STATE?", now_ms=1)

    assert state.startswith("STATE ")
