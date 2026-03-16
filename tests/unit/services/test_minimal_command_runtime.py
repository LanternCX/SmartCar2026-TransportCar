"""MinimalCommandRuntime 单元测试."""

import sys
import types
from typing import Any, cast

import pytest


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


def test_minimal_command_runtime_only_registers_health_tick_vision_queries() -> None:
    from services.runtime.minimal_command_runtime import MinimalCommandRuntime

    calls = []
    handlers_module = types.SimpleNamespace(
        QUERY_HANDLER_START_INDEX=18,
        load_query_handlers=lambda: calls.append("query"),
        load_command_handlers=lambda: calls.append("command"),
    )
    runtime = MinimalCommandRuntime(
        import_runtime_module=lambda _name: handlers_module,
        drop_stale_handler_modules=lambda start_index, stop_index=None: calls.append(
            (start_index, stop_index)
        ),
    )

    assert runtime.registered_query_tokens() == ("health", "tick", "vision")

    runtime.ensure_query_handlers()

    assert calls == [(18, None), "query"]


def test_transport_car_apply_command_activates_full_commands_via_runtime() -> None:
    from services.car import TransportCar

    calls = []
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.command_runtime = types.SimpleNamespace(
        activate_full_commands=lambda: calls.append("activate")
    )
    car._router = types.SimpleNamespace(
        route=lambda line, ctx: calls.append(("route", line, ctx.source))
    )
    car._build_handler_context = lambda source="uart6": types.SimpleNamespace(
        source=source
    )

    TransportCar.apply_command(car, "vx=1", source="uart3")

    assert calls == ["activate", ("route", "vx=1", "uart3")]
