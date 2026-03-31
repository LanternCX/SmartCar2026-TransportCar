def test_assistant_runtime_loop_closes_follow_timeout_and_state_chain() -> None:
    from assistant.app import AssistantRuntimeLoop

    class FakeUart:
        def __init__(self, lines=None):
            self.lines = list(lines or [])
            self.writes = []

        def read_line(self):
            if not self.lines:
                return None
            return self.lines.pop(0)

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeMotor:
        def __init__(self):
            self.last_duty = None

        def set_duty(self, duty):
            self.last_duty = duty

        def stop(self):
            self.last_duty = 0

    uart3 = FakeUart(
        [
            "follow=1,seq=8,valid=1,dx=0.10,dy=0.00",
            "STATE?",
        ]
    )
    motors = {"m": FakeMotor(), "l": FakeMotor(), "r": FakeMotor()}

    loop = AssistantRuntimeLoop({"uart3": uart3, "motors": motors})
    loop.step(now_ms=0)
    loop.step(now_ms=200)

    assert any(motor.last_duty is not None for motor in motors.values())
    assert "TIMEOUT,last_seq=8" in uart3.writes
    assert any(str(item).startswith("state=1,") for item in uart3.writes)
