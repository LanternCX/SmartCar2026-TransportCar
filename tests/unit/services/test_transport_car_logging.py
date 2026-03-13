"""TransportCar 日志接线单元测试."""

import sys
import types
from typing import Any, cast

import pytest

from diagnostics.sink import UartSink
from diagnostics.manager import LogManager
from services.commanding.context import TransportCommandContext
from services.commanding.session import CommandSession


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
    sys.modules["machine"] = machine

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
    sys.modules["seekfree"] = seekfree

    smartcar = types.ModuleType("smartcar")

    class FakeEncoder:
        def get(self):
            return 0

    def encoder(*_args, **_kwargs):
        return FakeEncoder()

    setattr(smartcar, "encoder", encoder)
    sys.modules["smartcar"] = smartcar


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
    car.vision_coordinator = types.SimpleNamespace(
        consume_uart_line=lambda *_args, **_kwargs: False
    )
    car.apply_command = lambda line, source="uart3": car._router.route(line, car)
    car._now_ms = lambda: 1000

    car._handle_uart_line("vx=1", source="uart3")

    assert car.uart3.messages[-1].startswith("I [services.comm+]")
    assert "RCV: vx=1" in car.uart3.messages[-1]


def test_transport_car_get_query_uart_defaults_to_uart6() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    uart6 = FakeUART()
    car.uart6 = uart6

    assert car.get_query_uart() is uart6


def test_transport_command_context_finalize_route_uses_runtime_public_methods() -> None:
    inverse_calls = []
    runtime = types.SimpleNamespace(
        command_session=CommandSession(),
        uart3=FakeUART(),
        logger_manager=LogManager(),
        chassis_state=types.SimpleNamespace(
            odometry=types.SimpleNamespace(x=1.0, y=2.0),
            heading_est=15.0,
            heading_target=30.0,
        ),
        now_ms=lambda: 1234,
        inverse_kinematics=lambda vx, vy, omega: inverse_calls.append((vx, vy, omega)),
        _now_ms=lambda: (_ for _ in ()).throw(
            AssertionError("should use public now_ms")
        ),
        _inverse_kinematics=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should use public inverse_kinematics")
        ),
    )
    runtime.command_session.last_cmd = {"vx": 1.0, "vy": -2.0, "omega": 3.0}

    ctx = TransportCommandContext(runtime, reply_uart=FakeUART(), source="uart6")

    ctx.finalize_route(set())

    assert inverse_calls == [(1.0, -2.0, 3.0)]


def test_transport_command_context_finalize_route_requires_public_runtime_methods() -> (
    None
):
    runtime = types.SimpleNamespace(
        command_session=CommandSession(),
        uart3=FakeUART(),
        logger_manager=LogManager(),
        chassis_state=types.SimpleNamespace(
            odometry=types.SimpleNamespace(x=1.0, y=2.0),
            heading_est=15.0,
            heading_target=30.0,
        ),
        _now_ms=lambda: 1234,
        _inverse_kinematics=lambda vx, vy, omega: (vx, vy, omega),
    )
    runtime.command_session.last_cmd = {"vx": 1.0, "vy": -2.0, "omega": 3.0}

    ctx = TransportCommandContext(runtime, reply_uart=FakeUART(), source="uart6")

    with pytest.raises(AttributeError):
        ctx.finalize_route(set())


def test_transport_command_context_reset_runtime_clears_vision_via_public_coordinator() -> (
    None
):
    clear_calls = []

    class FakeYawPid:
        def reset(self) -> None:
            return None

    runtime = types.SimpleNamespace(
        command_session=CommandSession(),
        uart3=FakeUART(),
        logger_manager=LogManager(),
        chassis_state=types.SimpleNamespace(
            odometry=types.SimpleNamespace(reset=lambda: None),
            heading_est=12.0,
            heading_target=18.0,
            yaw_pid=FakeYawPid(),
            yaw_integral=3.0,
            q_est=types.SimpleNamespace(w=0.0, x=1.0, y=2.0, z=3.0),
            last_yaw_rad=4.0,
            gyro_lpf=types.SimpleNamespace(reset=lambda _value: None),
            wheel_states=[],
        ),
        vision_coordinator=types.SimpleNamespace(
            clear_runtime=lambda: clear_calls.append("clear")
        ),
        _ensure_vision_coordinator=lambda: (_ for _ in ()).throw(
            AssertionError("should use public vision_coordinator")
        ),
    )

    ctx = TransportCommandContext(runtime, reply_uart=FakeUART(), source="uart6")

    ctx.reset_runtime()

    assert clear_calls == ["clear"]
