def _build_master_hw_bundle(uart3, uart6, uart8) -> dict:
    return {
        "uart": {"uart3": uart3, "uart6": uart6, "uart8": uart8},
        "motors": {},
        "encoders": {},
        "imu": object(),
    }


def test_master_runtime_loop_no_longer_reads_follow_vision_or_writes_uart3() -> None:
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

    uart6 = FakeUart(["v=1,s=1,x=12,y=-6"])
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop(
        _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    )
    result = loop.step(now_ms=100)

    assert set(result.keys()) == {"self_base_state"}
    assert uart3.writes == []
    assert uart3.read_count == 0
    assert uart6.read_count == 0
    assert uart8.read_count == 0


def test_master_runtime_loop_only_passes_runtime_clock_fields_to_app() -> None:
    from master.app import MasterRuntimeLoop

    class FakeUart:
        def __init__(self, lines=None):
            self.lines = list(lines or [])
            self.writes = []

        def read_line(self):
            raise AssertionError("旧跟随相机不应再被读取")

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeApp:
        def __init__(self, hw_bundle):
            self.hw_bundle = hw_bundle
            self.calls = []

        def step(self, observation):
            self.calls.append(dict(observation))
            return {
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
            }

    uart6 = FakeUart(["v=0,s=1"])
    uart8 = FakeUart()
    uart3 = FakeUart()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app = FakeApp(hw_bundle)

    loop = MasterRuntimeLoop(hw_bundle, app=app)
    result = loop.step(now_ms=100)

    assert result["phase"] == "IDLE"
    assert app.calls == [
        {
            "now_ms": 100,
            "run_motion": True,
            "cycle_token": app.calls[0]["cycle_token"],
        }
    ]
    assert uart3.writes == []


def test_master_runtime_loop_step_omits_internal_perf_diag() -> None:
    from master.app import MasterRuntimeLoop

    class FakeUart:
        def __init__(self, lines=None):
            self.lines = list(lines or [])
            self.writes = []

        def read_latest_line(self, transform=None):
            if not self.lines:
                return None
            line = self.lines.pop(0)
            if transform is None:
                return line
            return transform(line)

        def write_line(self, payload):
            self.writes.append(payload)

    class FakeApp:
        def __init__(self, hw_bundle):
            self.hw_bundle = hw_bundle

        def step(self, observation):
            return {
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
            }

    uart3 = FakeUart()
    uart6 = FakeUart(["v=1,s=1,x=12,y=-6"])
    uart8 = FakeUart()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    loop = MasterRuntimeLoop(hw_bundle, app=FakeApp(hw_bundle))

    result = loop.step(now_ms=100)

    assert result["phase"] == "IDLE"
    assert "perf_diag" not in result
    assert uart3.writes == []


def test_master_runtime_loop_keeps_passing_only_runtime_fields_across_steps() -> None:
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
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
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
    assert set(app.observations[0].keys()) == {"now_ms", "run_motion", "cycle_token"}
    assert app.observations[1]["now_ms"] == 200
    assert app.observations[1]["run_motion"] is True
    assert set(app.observations[1].keys()) == {"now_ms", "run_motion", "cycle_token"}
    assert first_result["phase"] == "IDLE"
    assert second_result["phase"] == "IDLE"
    assert uart3.writes == []
    assert uart6.read_count == 0
    assert uart8.read_count == 0


def test_master_runtime_loop_single_step_stays_free_of_removed_follow_inputs() -> None:
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
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
            }

    uart6 = FakeUart(["v=1,s=101,x=12,y=-6"])
    uart8 = FakeUart(["v=1,s=102,x=8,y=-4"])
    uart3 = FakeUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle

    loop = MasterRuntimeLoop(hw_bundle, app=app)

    result = loop.step(now_ms=100)

    assert result["phase"] == "IDLE"
    assert len(app.observations) == 1
    assert app.observations[0]["now_ms"] == 100
    assert app.observations[0]["run_motion"] is True
    assert set(app.observations[0].keys()) == {"now_ms", "run_motion", "cycle_token"}
    assert uart3.writes == []


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
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
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
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
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
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
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
                b"F,1,1",
                b",1.0,0.0\r\nPING\r\n",
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
    assert port.read_line() == "F,1,1,1.0,0.0"
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

    long_remote_line = "F,1,1," + ("x" * 170)

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


def test_master_uart_port_no_longer_exposes_removed_latest_line_reader() -> None:
    from master.hw.uart import UartPort

    port = UartPort(name="uart6", uart_id=6, baudrate=115200)

    assert not hasattr(port, "read_latest_line")


def test_master_hw_uart_module_no_longer_keeps_removed_follow_budget() -> None:
    import master.hw.uart as uart_module

    assert not hasattr(uart_module, "UART_READ_BUDGET_CHUNKS")


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


def test_master_runtime_loop_does_not_write_legacy_assistant_payload() -> None:
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
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
            }

    uart3 = FakeUart3()
    uart6 = FakeVisionUart()
    uart8 = FakeVisionUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle
    loop = MasterRuntimeLoop(hw_bundle, app=app)

    loop.step(now_ms=100)

    assert uart3.writes == []


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

    written = port.write_line("F,5,1,1,-2")

    assert device.writes == ["F,5,1,1,-2", "\r\n"]
    assert written == len(device.writes[0]) + len(device.writes[1])


def test_master_runtime_loop_runs_app_once_per_outer_step_without_follow_inputs() -> (
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
            self.calls = []
            self.hw_bundle = {}

        def step(self, observation):
            self.calls.append(dict(observation))
            return {
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
            }

    uart6 = FakeUart(["v=1,s=101,x=12,y=-6"])
    uart8 = FakeUart(["v=1,s=102,x=8,y=-4"])
    uart3 = FakeUart()
    app = FakeApp()
    hw_bundle = _build_master_hw_bundle(uart3=uart3, uart6=uart6, uart8=uart8)
    app.hw_bundle = hw_bundle
    loop = MasterRuntimeLoop(hw_bundle, app=app)

    result = loop.step(now_ms=100)

    assert result["phase"] == "IDLE"
    assert len(app.calls) == 1
    assert app.calls[0]["now_ms"] == 100
    assert app.calls[0]["run_motion"] is True
    assert set(app.calls[0].keys()) == {"now_ms", "run_motion", "cycle_token"}
    assert uart3.writes == []


def test_master_runtime_loop_no_longer_reads_assistant_feedback() -> None:
    from master.app import MasterRuntimeLoop

    state_line = (
        "state=1,state_label=TRACKING,last_seq=7,follow_active=1,"
        "heading_deg=1.000,target_heading_deg=1.000,yaw_rate_deg_s=0.000,"
        "odom_x=0.1000,odom_y=0.2000,base_ok=1"
    )

    class FakeUart3:
        def __init__(self) -> None:
            self.writes = []
            self.read_count = 0

        def read_line(self):
            self.read_count += 1
            raise AssertionError("旧辅车回包不应再被主车运行时读取")

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
                "selected_target": "idle",
                "phase": "IDLE",
                "self_target": {"kind": "hold"},
                "self_base_state": {
                    "heading_deg": 0.0,
                    "yaw_rate_deg_s": 0.0,
                    "odom_x": 0.0,
                    "odom_y": 0.0,
                    "base_ok": 0,
                },
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
    assert uart3.read_count == 0
    assert uart3.writes == []
