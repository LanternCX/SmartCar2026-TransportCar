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

    uart3 = FakeUart(
        [
            "follow=1,seq=8,valid=1,dx=0.10,dy=0.00",
        ]
    )
    motors = {"m": FakeMotor(), "l": FakeMotor(), "r": FakeMotor()}

    loop = AssistantRuntimeLoop(
        {
            "uart": {"uart3": uart3},
            "motors": motors,
            "encoders": {name: FakeEncoder(name) for name in ("m", "l", "r")},
            "imu": object(),
        }
    )
    loop.step(now_ms=0)
    loop.step(now_ms=50)
    loop.step(now_ms=200)

    assert any(motor.last_duty is not None for motor in motors.values())
    assert uart3.writes == ["OK,seq=8,valid=1"]


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

    uart3 = FakeUart(["follow=1,seq=8,valid=1,dx=0.10,dy=0.00"])
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
            "uart": {"uart3": uart3},
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
    assert uart3.writes == ["OK,seq=8,valid=1"]


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


def test_assistant_uart_read_latest_line_prefers_newest_complete_command() -> None:
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"follow=1,seq=1,valid=1,dx=0.1,dy=0.0\r\n",
                b"follow=1,seq=2,valid=1,dx=0.2,dy=0.0\r\n",
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

    assert port.read_latest_line() == "follow=1,seq=2,valid=1,dx=0.2,dy=0.0"


def test_assistant_uart_read_latest_line_drains_fragmented_backlog_in_one_call() -> (
    None
):
    from assistant.hw.uart import UartPort

    class FakeDevice:
        def __init__(self) -> None:
            self.chunks = [
                b"follow=1,seq=1,va",
                b"lid=1,dx=0.1,dy=0.0\r\n",
                b"follow=1,seq=2,va",
                b"lid=1,dx=0.2,dy=0.0\r\n",
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

    assert port.read_latest_line() == "follow=1,seq=2,valid=1,dx=0.2,dy=0.0"


def test_assistant_uart_drops_overlong_partial_line_and_resyncs() -> None:
    from assistant.hw.uart import UartPort

    valid_line = "follow=1,seq=3,valid=1,dx=0.3,dy=0.0"

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
                b"follow=1,seq=1,valid=1,dx=0.1,dy=0.0\r\n"
                b"follow=1,seq=2,valid=1,dx=0.2,dy=0.0\r\n"
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
