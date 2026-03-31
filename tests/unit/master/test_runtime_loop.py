def test_master_runtime_loop_reads_vision_and_writes_follow_command() -> None:
    from master.app import MasterRuntimeLoop

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

    uart6 = FakeUart(
        ["vision=1,camera_id=cam_a,seq=1,valid=1,target=follower,err_x=12,err_y=-6"]
    )
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3})
    result = loop.step(now_ms=100)

    assert result["assistant_command"] == "follow=1,seq=1,valid=1,dx=12.000,dy=-6.000"
    assert uart3.writes == ["follow=1,seq=1,valid=1,dx=12.000,dy=-6.000"]


def test_master_runtime_loop_writes_hold_when_no_target_is_available() -> None:
    from master.app import MasterRuntimeLoop

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

    uart6 = FakeUart(["vision=1,camera_id=cam_a,seq=1,valid=0,target=follower"])
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3})
    result = loop.step(now_ms=100)

    assert result["assistant_command"] == "follow=1,seq=1,valid=0,dx=0.000,dy=0.000"
    assert uart3.writes == ["follow=1,seq=1,valid=0,dx=0.000,dy=0.000"]


def test_master_uart_read_line_buffers_partial_and_returns_single_lines() -> None:
    from master.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"follow=1,seq=1",
                b",valid=1,dx=1.0,dy=0.0\r\nPING\r\n",
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
    assert port.read_line() == "PING"
