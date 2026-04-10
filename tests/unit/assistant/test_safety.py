def test_assistant_safety_triggers_stop_on_timeout() -> None:
    from assistant.safety import SafetyGuard

    guard = SafetyGuard(timeout_ms=100)
    guard.mark_command(0)

    assert guard.should_stop(150) is True


def test_assistant_safety_holds_estop_until_cleared() -> None:
    from assistant.safety import SafetyGuard

    guard = SafetyGuard(timeout_ms=100)
    guard.trigger_estop()

    assert guard.should_stop(10) is True

    guard.clear_estop()

    assert guard.should_stop(10) is False


def test_assistant_safety_disables_timeout_stop_when_timeout_not_positive() -> None:
    from assistant.safety import SafetyGuard

    guard = SafetyGuard(timeout_ms=0)
    guard.mark_command(0)

    assert guard.should_stop(10_000) is False
