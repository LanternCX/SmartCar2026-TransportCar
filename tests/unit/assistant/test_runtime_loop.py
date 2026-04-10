def test_assistant_runtime_loop_closes_follow_timeout_without_periodic_state_spam() -> (
    None
):
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

    class FakeEncoder:
        def __init__(self, name):
            self.name = name

        def read_and_clear(self):
            return 0.0

    uart3 = FakeUart([])
    uart6 = FakeUart(
        [
            "f=1,s=8,v=1,x=0.10,y=0.00",
        ]
    )
    motors = {"m": FakeMotor(), "l": FakeMotor(), "r": FakeMotor()}

    loop = AssistantRuntimeLoop(
        {
            "uart": {"uart3": uart3, "uart6": uart6},
            "motors": motors,
            "encoders": {name: FakeEncoder(name) for name in ("m", "l", "r")},
            "imu": object(),
        }
    )
    loop.step(now_ms=0)
    loop.step(now_ms=50)
    loop.step(now_ms=200)

    assert any(motor.last_duty is not None for motor in motors.values())
    assert uart3.writes == []
    assert uart6.writes == []


def test_assistant_runtime_loop_consumes_follow_command_from_uart6() -> None:
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

    class FakeEncoder:
        def __init__(self, name):
            self.name = name

        def read_and_clear(self):
            return 0.0

    uart3 = FakeUart([])
    uart6 = FakeUart(["f=1,s=8,v=1,x=0.10,y=0.00"])
    motors = {"m": FakeMotor(), "l": FakeMotor(), "r": FakeMotor()}

    loop = AssistantRuntimeLoop(
        {
            "uart": {"uart3": uart3, "uart6": uart6},
            "motors": motors,
            "encoders": {name: FakeEncoder(name) for name in ("m", "l", "r")},
            "imu": object(),
        }
    )
    loop.step(now_ms=0)

    assert any(motor.last_duty is not None for motor in motors.values())
    assert uart6.writes == []
    assert uart3.writes == []


def test_assistant_runtime_loop_writes_three_motor_outputs_for_follow_cycle(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

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

    class FakeEncoder:
        def __init__(self, name):
            self.name = name

        def read_and_clear(self):
            return 0.0

    uart3 = FakeUart([])
    uart6 = FakeUart(["f=1,s=8,v=1,x=0.10,y=0.00"])
    motors = {name: FakeMotor() for name in ("m", "l", "r")}

    monkeypatch.setattr(
        runtime,
        "update_heading_from_gyro",
        lambda state, heading_override=None: (
            setattr(state, "tick_s", 0.005),
            setattr(state, "heading_deg", 0.0),
            setattr(state, "yaw_rate_deg_s", 0.0),
        )[-1],
    )

    def _fake_apply_wheel_speed_control(state, wheel_targets, limit, motors=None):
        duty_map = {"m": -11, "l": 22, "r": -33}
        for name in ("m", "l", "r"):
            state.motor_duties[name] = duty_map[name]
            if motors is not None:
                motors[name].set_duty(duty_map[name])
        return dict(duty_map)

    monkeypatch.setattr(
        runtime, "apply_wheel_speed_control", _fake_apply_wheel_speed_control
    )

    loop = AssistantRuntimeLoop(
        {
            "uart": {"uart3": uart3, "uart6": uart6},
            "motors": motors,
            "encoders": {name: FakeEncoder(name) for name in ("m", "l", "r")},
            "imu": object(),
        }
    )

    loop.step(now_ms=0)

    assert {name: motor.last_duty for name, motor in motors.items()} == {
        "m": -11,
        "l": 22,
        "r": -33,
    }
    assert loop.app.runtime_state.motor_duties == {"m": -11, "l": 22, "r": -33}
    assert uart3.writes == []
    assert uart6.writes == []


def test_assistant_runtime_loop_uart6_keeps_same_follow_reply_shape(
    monkeypatch,
) -> None:
    import assistant.motion_runtime as runtime

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

    class FakeEncoder:
        def __init__(self, name):
            self.name = name

        def read_and_clear(self):
            return 0.0

    uart3 = FakeUart([])
    uart6 = FakeUart(["f=1,s=8,v=1,x=0.10,y=0.00"])
    motors = {name: FakeMotor() for name in ("m", "l", "r")}

    monkeypatch.setattr(
        runtime,
        "update_heading_from_gyro",
        lambda state, heading_override=None: (
            setattr(state, "tick_s", 0.005),
            setattr(state, "heading_deg", 0.0),
            setattr(state, "yaw_rate_deg_s", 0.0),
        )[-1],
    )

    def _fake_apply_wheel_speed_control(state, wheel_targets, limit, motors=None):
        duty_map = {"m": -11, "l": 22, "r": -33}
        for name in ("m", "l", "r"):
            state.motor_duties[name] = duty_map[name]
            if motors is not None:
                motors[name].set_duty(duty_map[name])
        return dict(duty_map)

    monkeypatch.setattr(
        runtime, "apply_wheel_speed_control", _fake_apply_wheel_speed_control
    )

    loop = AssistantRuntimeLoop(
        {
            "uart": {"uart3": uart3, "uart6": uart6},
            "motors": motors,
            "encoders": {name: FakeEncoder(name) for name in ("m", "l", "r")},
            "imu": object(),
        }
    )

    loop.step(now_ms=0)

    assert {name: motor.last_duty for name, motor in motors.items()} == {
        "m": -11,
        "l": 22,
        "r": -33,
    }
    assert loop.app.runtime_state.motor_duties == {"m": -11, "l": 22, "r": -33}
    assert uart6.writes == []
    assert uart3.writes == []


def test_assistant_runtime_loop_uart6_reads_latest_line_via_main_path() -> None:
    import types

    from assistant.app import AssistantRuntimeLoop
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"noise\r\n",
                b"f=1,s=10,v=1,x=0.1,y=0.0\r\n",
                b"f=1,s=11,v=1,x=0.2,y=0.0\r\n",
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

    class FakeReplyUart:
        def __init__(self) -> None:
            self.writes = []

        def write_line(self, payload):
            self.writes.append(payload)

    class DummyApp:
        def __init__(self, hw_bundle) -> None:
            self.hw_bundle = hw_bundle
            self.runtime_state = types.SimpleNamespace(hw_bundle=hw_bundle)
            self.lines = []

        def handle_line(self, line, now_ms, cycle_token=None):
            self.lines.append((line, now_ms, cycle_token))
            return "ACK"

        def tick(self, now_ms, cycle_token=None):
            return ""

    device = FakeDevice()
    uart6 = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(uart6, "_device", device)
    uart3 = FakeReplyUart()
    hw_bundle = {
        "uart": {"uart3": uart3, "uart6": uart6},
        "motors": {},
        "encoders": {},
        "imu": object(),
    }
    app = DummyApp(hw_bundle)
    loop = AssistantRuntimeLoop(hw_bundle, app=app)

    loop.step(now_ms=12)

    assert len(app.lines) == 1
    assert app.lines[0][0] == "f=1,s=10,v=1,x=0.1,y=0.0"
    assert app.lines[0][1] == 12
    assert app.lines[0][2] is not None
    assert uart3.writes == ["ACK"]
    assert device.read_count == 2


def test_assistant_runtime_loop_passes_full_hw_bundle_to_runtime_owner(
    monkeypatch,
) -> None:
    import types

    from assistant.app import AssistantRuntimeLoop

    captured = {"app_bundle": None}

    class DummyApp:
        def __init__(self, hw_bundle):
            captured["app_bundle"] = hw_bundle
            self.runtime_state = types.SimpleNamespace(hw_bundle=hw_bundle)

        def handle_line(self, line, now_ms):
            return ""

        def tick(self, now_ms):
            return ""

    hw_bundle = {
        "uart": {"uart3": object()},
        "motors": {name: object() for name in ("m", "l", "r")},
        "encoders": {name: object() for name in ("m", "l", "r")},
        "imu": object(),
    }

    monkeypatch.setattr("assistant.app.AssistantApp", DummyApp)
    loop = AssistantRuntimeLoop(hw_bundle)

    assert captured["app_bundle"] is hw_bundle
    assert loop.app.runtime_state.hw_bundle is hw_bundle
    assert tuple(sorted(loop.hw_bundle["motors"].keys())) == ("l", "m", "r")
    assert tuple(sorted(loop.hw_bundle["encoders"].keys())) == ("l", "m", "r")


def test_assistant_runtime_loop_rejects_mismatched_app_and_hw_bundle() -> None:
    import pytest

    from assistant.app import AssistantRuntimeLoop

    class DummyApp:
        def __init__(self, hw_bundle):
            self.hw_bundle = hw_bundle

        def handle_line(self, line, now_ms):
            return ""

        def tick(self, now_ms):
            return ""

    loop_bundle = {
        "uart": {"uart3": object()},
        "motors": {name: object() for name in ("m", "l", "r")},
        "encoders": {name: object() for name in ("m", "l", "r")},
        "imu": object(),
    }
    app_bundle = {
        "uart": {"uart3": object()},
        "motors": {name: object() for name in ("m", "l", "r")},
        "encoders": {name: object() for name in ("m", "l", "r")},
        "imu": object(),
    }

    with pytest.raises(ValueError, match="hw_bundle.*app"):
        AssistantRuntimeLoop(loop_bundle, app=DummyApp(hw_bundle=app_bundle))


def test_assistant_runtime_loop_rejects_runtime_owner_drift_under_same_app_bundle() -> (
    None
):
    import types
    import pytest

    from assistant.app import AssistantRuntimeLoop

    class DummyApp:
        def __init__(self, app_hw_bundle, runtime_hw_bundle):
            self.hw_bundle = app_hw_bundle
            self.runtime_state = types.SimpleNamespace(hw_bundle=runtime_hw_bundle)

        def handle_line(self, line, now_ms):
            return ""

        def tick(self, now_ms):
            return ""

    loop_bundle = {
        "uart": {"uart3": object()},
        "motors": {name: object() for name in ("m", "l", "r")},
        "encoders": {name: object() for name in ("m", "l", "r")},
        "imu": object(),
    }
    drifted_runtime_bundle = {
        "uart": {"uart3": object()},
        "motors": {name: object() for name in ("m", "l", "r")},
        "encoders": {name: object() for name in ("m", "l", "r")},
        "imu": object(),
    }

    with pytest.raises(ValueError, match="唯一 hw_bundle owner|同一套装配"):
        AssistantRuntimeLoop(
            loop_bundle,
            app=DummyApp(
                app_hw_bundle=loop_bundle,
                runtime_hw_bundle=drifted_runtime_bundle,
            ),
        )


def test_assistant_uart_read_line_buffers_partial_and_returns_single_lines() -> None:
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"f=1,s=1",
                b",v=1,x=1.0,y=0.0\r\nSTATE?\r\n",
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
    assert port.read_line() == "f=1,s=1,v=1,x=1.0,y=0.0"
    assert port.read_line() == "STATE?"


def test_assistant_uart_read_latest_line_prefers_newest_complete_command() -> None:
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"f=1,s=1,v=1,x=0.1,y=0.0\r\n",
                b"f=1,s=2,v=1,x=0.2,y=0.0\r\n",
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

    assert port.read_latest_line() == "f=1,s=2,v=1,x=0.2,y=0.0"


def test_assistant_uart_read_latest_line_drains_fragmented_backlog_in_one_call() -> (
    None
):
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"f=1,s=1,v=1,x=0",
                b".1,y=0.0\r\n",
                b"f=1,s=2,v=1,x=0",
                b".2,y=0.0\r\n",
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

    assert port.read_latest_line() == "f=1,s=2,v=1,x=0.2,y=0.0"


def test_assistant_uart_drops_overlong_partial_line_and_resyncs() -> None:
    from assistant.hw.uart import UartPort

    valid_line = "f=1,s=3,v=1,x=0.3,y=0.0"

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"x" * 257,
                b"overflow-tail\r\n" + valid_line.encode("utf-8") + b"\r\n",
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
    assert port.read_line() == valid_line


def test_assistant_uart_read_latest_line_limits_each_read_chunk() -> None:
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.buffer = bytearray(
                b"f=1,s=1,v=1,x=0.1,y=0.0\r\nf=1,s=2,v=1,x=0.2,y=0.0\r\n"
            )
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

    port.read_latest_line()

    assert device.read_sizes
    assert max(device.read_sizes) <= 96


def test_assistant_uart3_read_latest_line_has_no_two_chunk_budget() -> None:
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"noise\r\n",
                b"f=1,s=10,v=1,x=0.1,y=0.0\r\n",
                b"f=1,s=11,v=1,x=0.2,y=0.0\r\n",
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

    def _keep_follow_line(line):
        if not line.startswith("f="):
            return None
        return line

    device = FakeDevice()
    port = UartPort(name="uart3", uart_id=3, baudrate=115200)
    setattr(port, "_device", device)

    assert (
        port.read_latest_line(transform=_keep_follow_line) == "f=1,s=11,v=1,x=0.2,y=0.0"
    )
    assert device.read_count == 3


def test_assistant_uart6_read_latest_line_stops_after_two_chunk_budget() -> None:
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"noise\r\n",
                b"f=1,s=10,v=1,x=0.1,y=0.0\r\n",
                b"f=1,s=11,v=1,x=0.2,y=0.0\r\n",
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

    def _keep_follow_line(line):
        if not line.startswith("f="):
            return None
        return line

    device = FakeDevice()
    port = UartPort(name="uart6", uart_id=6, baudrate=115200)
    setattr(port, "_device", device)

    assert (
        port.read_latest_line(transform=_keep_follow_line) == "f=1,s=10,v=1,x=0.1,y=0.0"
    )
    assert device.read_count == 2
