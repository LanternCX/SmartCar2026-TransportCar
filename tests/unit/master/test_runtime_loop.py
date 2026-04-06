def _build_master_hw_bundle(uart3, uart6, uart8) -> dict:
    return {
        "uart": {"uart3": uart3, "uart6": uart6, "uart8": uart8},
        "motors": {},
        "encoders": {},
        "imu": object(),
    }


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

    uart6 = FakeUart(["v=1,s=1,x=12,y=-6"])
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop(
        _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    )
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

    uart6 = FakeUart(["v=0,s=1"])
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop(
        _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    )
    result = loop.step(now_ms=100)

    assert (
        result["assistant_command"]
        == "follow=1,seq=1,valid=0,dx=0.000,dy=0.000,reason=vision_invalid"
    )
    assert uart3.writes == [
        "follow=1,seq=1,valid=0,dx=0.000,dy=0.000,reason=vision_invalid"
    ]


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
            self.hw_bundle = {}

        def step(self, observation):
            self.observations.append(dict(observation))
            return {
                "assistant_command": "cmd-%d" % len(self.observations),
                "selected_target": "red",
                "phase": "TRACKING",
                "self_target": {"kind": "hold"},
            }

    uart6 = FakeUart(["v=1,s=101,x=12,y=-6"])
    uart8 = FakeUart(["v=1,s=102,x=8,y=-4"])
    uart3 = FakeUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle

    loop = MasterRuntimeLoop(hw_bundle, app=app)

    first_result = loop.step(now_ms=100)
    second_result = loop.step(now_ms=200)

    assert len(app.observations) == 2
    assert app.observations[0]["now_ms"] == 100
    assert app.observations[0]["run_motion"] is True
    assert isinstance(app.observations[0]["cycle_token"], object)
    assert app.observations[0]["observations"] == [
        {"uart": "uart6", "line": "v=1,s=101,x=12,y=-6"},
        {"uart": "uart8", "line": "v=1,s=102,x=8,y=-4"},
    ]
    assert app.observations[1]["now_ms"] == 200
    assert app.observations[1]["run_motion"] is True
    assert app.observations[1].get("observations") is None
    assert first_result["assistant_command"] == "cmd-1"
    assert second_result["assistant_command"] == "cmd-2"
    assert uart3.writes == ["cmd-1", "cmd-2"]
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
            self.hw_bundle = {}

        def step(self, observation):
            self.observations.append(dict(observation))
            return {
                "assistant_command": "cmd-%d" % len(self.observations),
                "selected_target": "red",
                "phase": "TRACKING",
                "self_target": {"kind": "hold"},
            }

    uart6 = FakeUart(["v=1,s=101,x=12,y=-6"])
    uart8 = FakeUart(["v=1,s=102,x=8,y=-4"])
    uart3 = FakeUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle

    loop = MasterRuntimeLoop(hw_bundle, app=app)

    result = loop.step(now_ms=100)

    assert result["assistant_command"] == "cmd-1"
    assert len(app.observations) == 1
    assert app.observations[0]["now_ms"] == 100
    assert app.observations[0]["run_motion"] is True
    assert app.observations[0]["observations"] == [
        {"uart": "uart6", "line": "v=1,s=101,x=12,y=-6"},
        {"uart": "uart8", "line": "v=1,s=102,x=8,y=-4"},
    ]
    assert uart3.writes == ["cmd-1"]


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
        def __init__(self, hw_bundle):
            captured["hw_bundle"] = hw_bundle
            self.hw_bundle = hw_bundle

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

    hw_bundle = _build_master_hw_bundle(
        uart3=uart_bundle["uart3"],
        uart6=uart_bundle["uart6"],
        uart8=uart_bundle["uart8"],
    )

    MasterRuntimeLoop(hw_bundle)

    assert captured["hw_bundle"] is hw_bundle
    assert captured["build_calls"] == 0


def test_master_runtime_loop_accepts_motion_state_owner_exposed_by_app() -> None:
    import types

    from master.app import MasterRuntimeLoop

    hw_bundle = _build_master_hw_bundle(
        uart3=object(),
        uart6=object(),
        uart8=object(),
    )

    class DummyApp:
        def __init__(self, runtime_hw_bundle):
            self.motion_state = types.SimpleNamespace(hw_bundle=runtime_hw_bundle)

        def step(self, observation):
            return {
                "assistant_command": "",
                "selected_target": "idle",
                "phase": "MARKER_MISSING",
                "self_target": {"kind": "hold"},
            }

    loop = MasterRuntimeLoop(hw_bundle, app=DummyApp(runtime_hw_bundle=hw_bundle))

    assert loop.hw_bundle is hw_bundle


def test_master_runtime_loop_rejects_runtime_owner_drift_under_same_app_bundle() -> (
    None
):
    import types

    import pytest

    from master.app import MasterRuntimeLoop

    loop_bundle = _build_master_hw_bundle(
        uart3=object(),
        uart6=object(),
        uart8=object(),
    )
    drifted_runtime_bundle = _build_master_hw_bundle(
        uart3=object(),
        uart6=object(),
        uart8=object(),
    )

    class DummyApp:
        def __init__(self, app_hw_bundle, runtime_hw_bundle):
            self.hw_bundle = app_hw_bundle
            self.motion_state = types.SimpleNamespace(hw_bundle=runtime_hw_bundle)

        def step(self, observation):
            return {
                "assistant_command": "",
                "selected_target": "idle",
                "phase": "MARKER_MISSING",
                "self_target": {"kind": "hold"},
            }

    with pytest.raises(ValueError, match="唯一 hw_bundle owner|同一套完整装配"):
        MasterRuntimeLoop(
            loop_bundle,
            app=DummyApp(
                app_hw_bundle=loop_bundle,
                runtime_hw_bundle=drifted_runtime_bundle,
            ),
        )


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


def test_master_vision_uart_drops_overlong_partial_line_and_resyncs() -> None:
    from master.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                (b"x" * 161),
                (b"overflow-tail\r\nv=1,s=1,x=1,y=2\r\n"),
            ]

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", FakeDevice())

    assert port.read_line() is None
    assert port.read_line() == "v=1,s=1,x=1,y=2"


def test_master_uart3_keeps_long_remote_line_without_vision_drop_rule() -> None:
    from master.hw.uart import UartPort

    long_remote_line = "follow=1,seq=1," + ("x" * 170)

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [long_remote_line.encode("utf-8") + b"\r\n"]

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

    assert port.read_line() == long_remote_line


def test_master_uart3_drops_overlong_partial_line_and_resyncs() -> None:
    from master.hw.uart import UartPort

    state_line = (
        "state=1,state_label=TRACKING,last_seq=7,follow_active=1,"
        "heading_deg=1.000,target_heading_deg=1.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.1000,odom_y=0.2000,base_ok=1"
    )

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"x" * 257,
                b"overflow-tail\r\n" + state_line.encode("utf-8") + b"\r\n",
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
    assert port.read_line() == state_line


def test_master_vision_uart_accepts_exact_160_chars_before_crlf() -> None:
    from master.hw.uart import UartPort

    valid_line = "v" * 160

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [valid_line.encode("utf-8") + b"\r\n"]

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", FakeDevice())

    assert port.read_line() == valid_line


def test_master_uart_read_line_works_when_buffer_disallows_delete() -> None:
    from master.hw.uart import UartPort

    class NoDeleteBuffer(bytearray):
        def __delitem__(self, key):
            raise TypeError("bytearray object doesn't support item deletion")

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [b"PING\r\n"]

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    port._read_buffer = NoDeleteBuffer()
    setattr(port, "_device", FakeDevice())

    assert port.read_line() == "PING"


def test_master_vision_uart_read_latest_line_drains_backlog_and_keeps_latest() -> None:
    from master.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.buffer = bytearray(b"v=1,s=1,x=1,y=2\r\nv=1,s=2,x=3,y=4\r\n")

        def any(self) -> int:
            return len(self.buffer)

        def read(self, size=None):
            if not self.buffer:
                return None
            if size is None:
                size = len(self.buffer)
            chunk = bytes(self.buffer[:size])
            del self.buffer[:size]
            return chunk

    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", FakeDevice())

    assert port.read_latest_line() == "v=1,s=2,x=3,y=4"
    assert port.read_latest_line() is None


def test_master_vision_uart_read_latest_line_limits_each_read_chunk() -> None:
    from master.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.buffer = bytearray(b"v=1,s=1,x=1,y=2\r\nv=1,s=2,x=3,y=4\r\n")
            self.read_sizes = []

        def any(self) -> int:
            return len(self.buffer)

        def read(self, size=None):
            self.read_sizes.append(size)
            if not self.buffer:
                return None
            if size is None:
                size = len(self.buffer)
            chunk = bytes(self.buffer[:size])
            del self.buffer[:size]
            return chunk

    device = FakeDevice()
    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", device)

    port.read_latest_line()

    assert device.read_sizes
    assert max(device.read_sizes) <= 96


def test_master_vision_uart_read_latest_line_skips_bad_lines_and_keeps_last_valid() -> (
    None
):
    from master.hw.uart import UartPort
    from master.vision.parser import parse_vision_line

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"=281,x=9,y=45\r\nv=1,s=297,x=9,y=46\r\n",
                b"vv=1,s=327,x=9,y=46\r\nv=1,s=328,x=10,y=47\r\n",
            ]

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    def _keep_valid_visual_line(line):
        try:
            parse_vision_line(line)
        except ValueError:
            return None
        return line

    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", FakeDevice())

    assert (
        port.read_latest_line(transform=_keep_valid_visual_line)
        == "v=1,s=328,x=10,y=47"
    )


def test_master_vision_uart_read_latest_line_returns_none_when_tick_has_only_bad_lines() -> (
    None
):
    from master.hw.uart import UartPort
    from master.vision.parser import parse_vision_line

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [b"=281,x=9,y=45\r\nvv=1,s=327,x=9,y=46\r\n"]

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    def _keep_valid_visual_line(line):
        try:
            parse_vision_line(line)
        except ValueError:
            return None
        return line

    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", FakeDevice())

    assert port.read_latest_line(transform=_keep_valid_visual_line) is None


def test_master_vision_uart_read_latest_line_stops_after_small_fixed_budget() -> None:
    from master.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"v=1,s=1,x=1,y=1\r\n",
                b"v=1,s=2,x=2,y=2\r\n",
                b"v=1,s=3,x=3,y=3\r\n",
            ]
            self.read_count = 0

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            self.read_count += 1
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    device = FakeDevice()
    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", device)

    assert port.read_latest_line() == "v=1,s=2,x=2,y=2"
    assert device.read_count == 2
    assert len(device.chunks) == 1


def test_master_uart3_read_line_limits_each_read_chunk() -> None:
    from master.hw.uart import UartPort

    state_line = (
        "state=1,state_label=TRACKING,last_seq=12345,follow_active=1,"
        "heading_deg=-180.000,target_heading_deg=-180.000,yaw_rate_deg_s=-999.999,"
        "odom_x=-123.4567,odom_y=-123.4567,base_ok=1"
    )

    class FakeDevice:
        def __init__(self) -> None:
            self.buffer = bytearray(state_line.encode("utf-8") + b"\r\n")
            self.read_sizes = []

        def any(self) -> int:
            return len(self.buffer)

        def read(self, size=None):
            self.read_sizes.append(size)
            if not self.buffer:
                return None
            if size is None:
                size = len(self.buffer)
            chunk = bytes(self.buffer[:size])
            del self.buffer[:size]
            return chunk

    device = FakeDevice()
    port = UartPort(name="uart3", uart_id=3, baudrate=115200)
    setattr(port, "_device", device)

    assert port.read_line() is None
    assert port.read_line() == state_line
    assert device.read_sizes
    assert max(device.read_sizes) <= 96


def test_master_uart3_read_latest_line_keeps_last_valid_state_when_tail_is_invalid() -> (
    None
):
    from master.hw.uart import UartPort
    from master.protocol import parse_assistant_state

    state_line = (
        "state=1,state_label=TRACKING,last_seq=7,follow_active=1,"
        "heading_deg=1.000,target_heading_deg=1.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.1000,odom_y=0.2000,base_ok=1"
    )

    class FakeDevice:
        def __init__(self) -> None:
            self.buffer = bytearray(
                state_line.encode("utf-8") + b"\r\n" + b"noise-without-state=1\r\n"
            )

        def any(self) -> int:
            return len(self.buffer)

        def read(self, size=None):
            if not self.buffer:
                return None
            if size is None:
                size = len(self.buffer)
            chunk = bytes(self.buffer[:size])
            del self.buffer[:size]
            return chunk

    port = UartPort(name="uart3", uart_id=3, baudrate=115200)
    setattr(port, "_device", FakeDevice())

    assert port.read_latest_line(transform=parse_assistant_state) == {
        "state_label": "TRACKING",
        "last_seq": 7,
        "follow_active": 1,
        "heading_deg": 1.0,
        "target_heading_deg": 1.0,
        "yaw_rate_deg_s": 0.0,
        "odom_x": 0.1,
        "odom_y": 0.2,
        "base_ok": 1,
    }


def test_master_uart3_read_latest_line_still_drains_all_available_chunks() -> None:
    from master.hw.uart import UartPort
    from master.protocol import parse_assistant_state

    first_state_line = (
        "state=1,state_label=TRACKING,last_seq=7,follow_active=1,"
        "heading_deg=1.000,target_heading_deg=1.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.1000,odom_y=0.2000,base_ok=1"
    )
    last_state_line = (
        "state=1,state_label=TRACKING,last_seq=9,follow_active=1,"
        "heading_deg=3.000,target_heading_deg=3.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.3000,odom_y=0.4000,base_ok=1"
    )

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                first_state_line.encode("utf-8") + b"\r\n",
                b"noise-without-state=1\r\n",
                last_state_line.encode("utf-8") + b"\r\n",
            ]
            self.read_count = 0

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            self.read_count += 1
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    device = FakeDevice()
    port = UartPort(name="uart3", uart_id=3, baudrate=115200)
    setattr(port, "_device", device)

    assert port.read_latest_line(transform=parse_assistant_state) == {
        "state_label": "TRACKING",
        "last_seq": 9,
        "follow_active": 1,
        "heading_deg": 3.0,
        "target_heading_deg": 3.0,
        "yaw_rate_deg_s": 0.0,
        "odom_x": 0.3,
        "odom_y": 0.4,
        "base_ok": 1,
    }
    assert device.read_count == 3


def test_master_uart3_read_latest_line_propagates_parse_failure_from_transform() -> (
    None
):
    from master.hw.uart import UartPort
    from master.vision.parser import parse_vision_line

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [b"=281,x=9,y=45\r\n"]

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

    import pytest

    with pytest.raises(ValueError, match="empty_key"):
        port.read_latest_line(transform=parse_vision_line)


def test_master_runtime_loop_drops_invalid_vision_line_before_app() -> None:
    from master.app import MasterRuntimeLoop

    class FakeVisionUart:
        def read_latest_line(self, transform=None):
            assert transform is not None
            return transform("=281,x=9,y=45")

    class FakeUart3:
        def __init__(self) -> None:
            self.writes = []

        def read_latest_line(self, transform=None):
            return None

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeApp:
        def __init__(self):
            self.calls = []
            self.hw_bundle = {}

        def step(self, observation):
            self.calls.append(dict(observation))
            return {
                "assistant_command": "cmd-hold",
                "selected_target": "idle",
                "phase": "MARKER_MISSING",
                "self_target": {"kind": "hold"},
            }

    uart3 = FakeUart3()
    uart6 = FakeVisionUart()
    uart8 = FakeVisionUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle
    loop = MasterRuntimeLoop(hw_bundle, app=app)

    loop.step(now_ms=100)

    assert app.calls == [
        {
            "now_ms": 100,
            "run_motion": True,
            "cycle_token": app.calls[0]["cycle_token"],
        }
    ]


def test_master_runtime_loop_reads_latest_valid_vision_line_through_uart_port() -> None:
    from master.app import MasterRuntimeLoop
    from master.hw.uart import UartPort

    class FakeVisionDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"=281,x=9,y=45\r\nv=1,s=297,x=9,y=46\r\n",
                b"vv=1,s=327,x=9,y=46\r\nv=1,s=328,x=10,y=47\r\n",
            ]

        def any(self) -> int:
            if not self.chunks:
                return 0
            return len(self.chunks[0])

        def read(self, size=None):
            if not self.chunks:
                return None
            return self.chunks.pop(0)

    class FakeUart3:
        def __init__(self) -> None:
            self.writes = []

        def read_latest_line(self, transform=None):
            return None

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeApp:
        def __init__(self):
            self.calls = []
            self.hw_bundle = {}

        def step(self, observation):
            self.calls.append(dict(observation))
            return {
                "assistant_command": "cmd-hold",
                "selected_target": "idle",
                "phase": "MARKER_MISSING",
                "self_target": {"kind": "hold"},
            }

    uart3 = FakeUart3()
    uart6 = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(uart6, "_device", FakeVisionDevice())
    uart8 = UartPort(name="uart8", uart_id=8, baudrate=115200)
    setattr(uart8, "_device", FakeVisionDevice())
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle
    loop = MasterRuntimeLoop(hw_bundle, app=app)

    loop.step(now_ms=100)

    assert app.calls == [
        {
            "now_ms": 100,
            "run_motion": True,
            "cycle_token": app.calls[0]["cycle_token"],
            "observations": [
                {"uart": "uart6", "line": "v=1,s=328,x=10,y=47"},
                {"uart": "uart8", "line": "v=1,s=328,x=10,y=47"},
            ],
        }
    ]


def test_master_runtime_loop_writes_only_assistant_command() -> None:
    from master.app import MasterRuntimeLoop

    class FakeVisionUart:
        def read_latest_line(self, transform=None):
            return None

    class FakeUart3:
        def __init__(self) -> None:
            self.writes = []

        def read_latest_line(self, transform=None):
            return None

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeApp:
        def __init__(self):
            self.hw_bundle = {}

        def step(self, observation):
            return {
                "assistant_debug_line": "debug_parse_invalid=1",
                "assistant_command": "cmd-final",
                "selected_target": "idle",
                "phase": "MARKER_MISSING",
                "self_target": {"kind": "hold"},
            }

    uart3 = FakeUart3()
    uart6 = FakeVisionUart()
    uart8 = FakeVisionUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle
    loop = MasterRuntimeLoop(hw_bundle, app=app)

    loop.step(now_ms=100)

    assert uart3.writes == ["cmd-final"]


def test_master_uart_write_line_writes_payload_and_crlf_separately() -> None:
    from master.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.writes = []

        def write(self, payload):
            self.writes.append(payload)
            return len(payload)

    device = FakeDevice()
    port = UartPort(name="uart3", uart_id=3, baudrate=115200)
    setattr(port, "_device", device)

    written = port.write_line("follow=1,seq=5,valid=1,dx=1.000,dy=-2.000")

    assert device.writes == ["follow=1,seq=5,valid=1,dx=1.000,dy=-2.000", "\r\n"]
    assert written == len(device.writes[0]) + len(device.writes[1])


def test_master_runtime_loop_runs_complete_chain_once_per_outer_step() -> None:
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
            self.calls = []
            self.hw_bundle = {}

        def step(self, observation):
            self.calls.append(dict(observation))
            return {
                "assistant_command": "cmd-once",
                "selected_target": "red",
                "phase": "TRACKING",
                "self_target": {"kind": "hold"},
            }

    uart6 = FakeUart(["v=1,s=101,x=12,y=-6"])
    uart8 = FakeUart(["v=1,s=102,x=8,y=-4"])
    uart3 = FakeUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle
    loop = MasterRuntimeLoop(hw_bundle, app=app)

    result = loop.step(now_ms=100)

    assert result["assistant_command"] == "cmd-once"
    assert len(app.calls) == 1
    assert app.calls[0]["now_ms"] == 100
    assert app.calls[0]["run_motion"] is True
    assert app.calls[0]["observations"] == [
        {"uart": "uart6", "line": "v=1,s=101,x=12,y=-6"},
        {"uart": "uart8", "line": "v=1,s=102,x=8,y=-4"},
    ]
    assert uart3.writes == ["cmd-once"]


def test_master_runtime_loop_prefers_latest_assistant_feedback_line() -> None:
    from master.app import MasterRuntimeLoop

    state_line = (
        "state=1,state_label=TRACKING,last_seq=7,follow_active=1,"
        "heading_deg=1.000,target_heading_deg=1.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.1000,odom_y=0.2000,base_ok=1"
    )

    class FakeUart3:
        def __init__(self) -> None:
            self.writes = []

        def read_line(self):
            return None

        def read_latest_line(self, transform=None):
            if transform is None:
                return state_line
            return transform(state_line)

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeVisionUart:
        def read_latest_line(self, transform=None):
            return None

    class FakeApp:
        def __init__(self):
            self.calls = []
            self.hw_bundle = {}

        def step(self, observation):
            self.calls.append(dict(observation))
            return {
                "assistant_command": "cmd-once",
                "selected_target": "idle",
                "phase": "MARKER_MISSING",
                "self_target": {"kind": "hold"},
            }

    uart3 = FakeUart3()
    uart6 = FakeVisionUart()
    uart8 = FakeVisionUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle
    loop = MasterRuntimeLoop(hw_bundle, app=app)

    loop.step(now_ms=100)

    assert app.calls == [
        {
            "now_ms": 100,
            "run_motion": True,
            "cycle_token": app.calls[0]["cycle_token"],
            "assistant_feedback": {
                "state_label": "TRACKING",
                "last_seq": 7,
                "follow_active": 1,
                "heading_deg": 1.0,
                "target_heading_deg": 1.0,
                "yaw_rate_deg_s": 0.0,
                "odom_x": 0.1,
                "odom_y": 0.2,
                "base_ok": 1,
            },
        }
    ]
    assert uart3.writes == ["cmd-once"]
