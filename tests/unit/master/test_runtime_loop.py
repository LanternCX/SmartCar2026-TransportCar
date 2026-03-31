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


def test_master_runtime_loop_continues_polling_vision_and_writing_controls() -> None:
    from master.app import MasterRuntimeLoop

    class FakeUart:
        def __init__(self, lines=None):
            self.lines = list(lines or [])
            self.writes = []
            self.read_count = 0

        def read_line(self):
            self.read_count += 1
            if not self.lines:
                return None
            return self.lines.pop(0)

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeApp:
        def __init__(self):
            self.observations = []

        def step(self, observation):
            self.observations.append(dict(observation))
            return {
                "assistant_command": "cmd-%d" % len(self.observations),
                "selected_target": "follower",
                "phase": "TRACKING",
                "self_target": {"kind": "hold"},
            }

    uart6 = FakeUart(["vision-from-uart6"])
    uart8 = FakeUart(["vision-from-uart8"])
    uart3 = FakeUart()
    app = FakeApp()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3}, app=app)

    first_result = loop.step(now_ms=100)
    second_result = loop.step(now_ms=200)

    assert app.observations == [
        {"uart": "uart6", "line": "vision-from-uart6", "now_ms": 100},
        {"uart": "uart8", "line": "vision-from-uart8", "now_ms": 100},
        {"now_ms": 200},
    ]
    assert first_result["assistant_command"] == "cmd-2"
    assert second_result["assistant_command"] == "cmd-3"
    assert uart3.writes == ["cmd-2", "cmd-3"]
    assert uart6.read_count == 2
    assert uart8.read_count == 2


def test_master_runtime_loop_writes_once_when_same_tick_receives_two_vision_inputs() -> (
    None
):
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

    class FakeApp:
        def __init__(self):
            self.observations = []

        def step(self, observation):
            self.observations.append(dict(observation))
            return {
                "assistant_command": "cmd-%d" % len(self.observations),
                "selected_target": "follower",
                "phase": "TRACKING",
                "self_target": {"kind": "hold"},
            }

    uart6 = FakeUart(["vision-from-uart6"])
    uart8 = FakeUart(["vision-from-uart8"])
    uart3 = FakeUart()
    app = FakeApp()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3}, app=app)

    result = loop.step(now_ms=100)

    assert result["assistant_command"] == "cmd-2"
    assert app.observations == [
        {"uart": "uart6", "line": "vision-from-uart6", "now_ms": 100},
        {"uart": "uart8", "line": "vision-from-uart8", "now_ms": 100},
    ]
    assert uart3.writes == ["cmd-2"]


def test_master_runtime_loop_reuses_provided_uart_bundle_for_default_app(
    monkeypatch,
) -> None:
    from master.app import MasterRuntimeLoop

    captured = {"uart_bundle": None, "build_calls": 0}
    uart_bundle = {
        "uart3": object(),
        "uart6": object(),
        "uart8": object(),
    }

    class DummyApp:
        def __init__(self, uart_bundle):
            captured["uart_bundle"] = uart_bundle

        def step(self, observation):
            return {
                "assistant_command": "",
                "selected_target": "idle",
                "phase": "MARKER_MISSING",
                "self_target": {"kind": "hold"},
            }

    def _unexpected_build_hw_bundle():
        captured["build_calls"] += 1
        return {
            "uart": uart_bundle,
            "motors": {},
            "encoders": {},
            "imu": object(),
        }

    monkeypatch.setattr("master.app.MasterApp", DummyApp)
    monkeypatch.setattr("master.app.build_hw_bundle", _unexpected_build_hw_bundle)

    MasterRuntimeLoop(uart_bundle)

    assert captured["uart_bundle"] is uart_bundle
    assert captured["build_calls"] == 0


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
