"""TransportCar 日志接线单元测试."""

import sys
import types
from typing import Any, cast

import pytest

from diagnostics.sink import UartSink
from diagnostics.manager import LogManager


pytestmark = pytest.mark.unit


def _install_transport_stubs() -> None:
    machine = types.ModuleType("machine")

    class Pin:
        OUT = 0
        IN = 1
        PULL_UP_47K = 2

        def __init__(self, *_args, **_kwargs):
            self._value = 1

        def value(self):
            return self._value

        def toggle(self):
            return None

    class UART:
        def __init__(self, *_args, **_kwargs):
            self.messages = []

        def init(self, *_args, **_kwargs):
            return None

        def write(self, text):
            self.messages.append(text)

        def any(self):
            return 0

        def read(self, _size):
            return b""

    setattr(machine, "Pin", Pin)
    setattr(machine, "UART", UART)
    sys.modules.setdefault("machine", machine)

    seekfree = types.ModuleType("seekfree")

    class MOTOR_CONTROLLER:
        PWM_C30_DIR_C31 = 1
        PWM_D4_DIR_D5 = 2
        PWM_D6_DIR_D7 = 3

        def __init__(self, *_args, **_kwargs):
            self.last_duty = 0

        def duty(self, value):
            self.last_duty = value

    class IMU660RX:
        def get(self):
            return [0, 0, 0, 0, 0, 0]

    setattr(seekfree, "MOTOR_CONTROLLER", MOTOR_CONTROLLER)
    setattr(seekfree, "IMU660RX", IMU660RX)
    sys.modules.setdefault("seekfree", seekfree)

    smartcar = types.ModuleType("smartcar")

    class FakeEncoder:
        def get(self):
            return 0

    def encoder(*_args, **_kwargs):
        return FakeEncoder()

    setattr(smartcar, "encoder", encoder)
    sys.modules.setdefault("smartcar", smartcar)


_install_transport_stubs()

import services.transport_car as transport_car_module  # noqa: E402


class FakeUART:
    """测试串口假对象."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def write(self, text: str) -> None:
        self.messages.append(text)

    def any(self) -> int:
        return 0

    def read(self, _size: int) -> bytes:
        return b""


class FakeRouter:
    """测试路由器假对象."""

    def __init__(self) -> None:
        self.routed: list[tuple[str, object]] = []

    def route(self, line: str, ctx: object) -> None:
        self.routed.append((line, ctx))


def _build_test_logger_manager(uart: object) -> LogManager:
    return LogManager(sinks=[cast(Any, UartSink(cast(Any, uart)))])


def test_transport_car_boot_logs_go_through_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uart3 = FakeUART()
    uart6 = FakeUART()
    monkeypatch.setattr(transport_car_module, "create_uart3", lambda: uart3)
    monkeypatch.setattr(transport_car_module, "create_uart6", lambda: uart6)
    monkeypatch.setattr(
        transport_car_module,
        "create_imu",
        lambda: types.SimpleNamespace(get=lambda: [0.0] * 6),
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_motors",
        lambda: {
            name: types.SimpleNamespace(duty=lambda _value: None)
            for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_encoders",
        lambda: {
            name: types.SimpleNamespace(get=lambda: 0.0) for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    transport_car_module.TransportCar()

    assert uart3.messages[0].startswith("I [system.boot")
    assert any("System Starting" in line for line in uart3.messages)


def test_transport_car_error_path_uses_structured_error_log() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()
    car.logger_manager = _build_test_logger_manager(car.uart3)
    car.log_health = car.logger_manager.get_logger("system.health")
    car.last_exception_text = "none"

    car._emit_error_log("imu init failed")

    assert car.last_exception_text == "imu init failed"
    assert car.uart3.messages[-1].startswith("E [system.health")
    assert "imu init failed" in car.uart3.messages[-1]


def test_transport_car_uart3_command_echo_uses_command_logger() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()
    car.logger_manager = _build_test_logger_manager(car.uart3)
    car.log_command = car.logger_manager.get_logger("services.command")
    car._router = FakeRouter()
    car.vision_protocol = types.SimpleNamespace(
        try_parse_observation=lambda *_args, **_kwargs: types.SimpleNamespace(
            consumed=False
        )
    )
    car.apply_command = lambda line: car._router.route(line, car)

    car._handle_uart_line("vx=1", source="uart3")

    assert car.uart3.messages[-1].startswith("I [services.comm+]")
    assert "RCV: vx=1" in car.uart3.messages[-1]
