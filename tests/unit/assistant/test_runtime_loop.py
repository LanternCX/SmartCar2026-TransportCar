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


def test_assistant_uart_read_line_buffers_partial_and_returns_single_lines() -> None:
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"follow=1,seq=1",
                b",valid=1,dx=1.0,dy=0.0\r\nSTATE?\r\n",
            ]

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    port = UartPort(name="uart3", uart_id=3, baudrate=115200)
    setattr(port, "_device", FakeDevice())

    assert port.read_line() is None
    assert port.read_line() == "follow=1,seq=1,valid=1,dx=1.0,dy=0.0"
    assert port.read_line() == "STATE?"
