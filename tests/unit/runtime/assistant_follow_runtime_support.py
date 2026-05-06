"""辅车角色运行时测试辅助模块.

@file tests/unit/runtime/assistant_follow_runtime_support.py
"""

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Optional
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


def import_assistant_module(module_name: str, monkeypatch):
    """按正常包路径导入辅车视觉运行模块."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for loaded_name in (
        "vision.assistant",
        "vision.assistant.follow_runtime",
        module_name,
    ):
        sys.modules.pop(loaded_name, None)
    return import_module(module_name)


class FakeClock:
    """提供可手动推进的毫秒时钟桩."""

    def __init__(self, initial_ms: int = 0) -> None:
        self.now_ms = initial_ms

    def advance(self, delta_ms: int) -> None:
        self.now_ms += delta_ms

    def __call__(self) -> int:
        return self.now_ms


class _FakeUart:
    def __init__(self, incoming_lines=()) -> None:
        self._buffer = "".join("%s\n" % line for line in incoming_lines).encode()
        self.messages = []
        self.read_sizes = []
        self.read_error: Optional[BaseException] = None

    def any(self) -> int:
        return len(self._buffer)

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        self.read_sizes.append(size)
        chunk = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return chunk

    def write(self, text) -> None:
        self.messages.append(text)


def install_fake_transport_car(monkeypatch):
    """注入共享底盘最小桩对象."""

    events = []
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")
    uart3 = _FakeUart()
    uart8 = _FakeUart()

    class _TransportCar:
        def __init__(self) -> None:
            self.wheel_states = [{"encoder": "enc-left"}, {"encoder": "enc-right"}]
            self.imu = "imu"
            self.ticker = None
            self.uart3 = uart3
            self.uart8 = uart8
            self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            self.last_chassis_target = {
                "source": None,
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "has_omega": False,
            }
            self.orbit_mode = False
            self.orbit_radius_scale = 1.0
            self.command_lock = False
            self.complete_orbit_on_next_step = False
            self.command_mode = "none"
            self._process_uart = self._original_process_uart

        def _original_process_uart(self) -> None:
            events.append("transport_process_uart")

        def mark_tick(self, tick=None) -> None:
            events.append(("mark_tick", tick))

        def set_ticker(self, ticker_obj) -> None:
            self.ticker = ticker_obj
            events.append(("set_ticker", ticker_obj))

        def step(self) -> bool:
            if self.complete_orbit_on_next_step:
                self.complete_orbit_on_next_step = False
                self.command_lock = False
                self.orbit_mode = False
                self.command_mode = "none"
                self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            events.append("transport_step")
            return False

        def handle_velocity_packet(self, vx: float, vy: float, omega: float, source: str, has_omega=True) -> None:
            events.append(("handle_velocity", source, vx, vy, omega))
            self.last_chassis_target = {
                "source": source,
                "vx": float(vx),
                "vy": float(vy),
                "omega": float(omega),
                "has_omega": bool(has_omega),
            }
            self.control_state["vx"] = float(vx)
            self.control_state["vy"] = float(vy)
            self.control_state.pop("x", None)
            self.control_state.pop("y", None)
            if has_omega:
                self.control_state["omega"] = float(omega)
                self.control_state.pop("angle", None)
            self.command_lock = False
            self.command_mode = "none"

        def set_orbit_target(self, target_angle_deg: float, radius_scale: float) -> None:
            events.append(("set_orbit_target", float(target_angle_deg), float(radius_scale)))
            self.control_state = {
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "angle": float(target_angle_deg),
            }
            self.command_lock = True
            self.command_mode = "locked"
            self.orbit_mode = True
            self.orbit_radius_scale = float(radius_scale)

        def set_heading_target(self, target_angle_deg: float) -> None:
            events.append(("set_heading_target", float(target_angle_deg)))
            self.control_state["omega"] = 0.0
            self.control_state["angle"] = float(target_angle_deg)
            self.command_lock = True
            self.command_mode = "locked"
            self.orbit_mode = False

        def set_relative_translation_target(self, dx: float, dy: float) -> None:
            events.append(("set_relative_translation_target", float(dx), float(dy)))
            self.control_state = {
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "angle": 0.0,
                "x": float(dx),
                "y": float(dy),
            }
            self.command_lock = True
            self.command_mode = "locked"
            self.orbit_mode = False

        def build_health_snapshot(self) -> dict:
            return {"alive": 1, "last_err": "none"}

    monkeypatch.setitem(sys.modules, "core", core_package)
    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core.runtime", core_module)

    hardware_package = ModuleType("hardware")
    uart_bus_module = ModuleType("hardware.uart_bus")
    setattr(uart_bus_module, "create_uart8", lambda: uart8)
    setattr(uart_bus_module, "create_uart6", lambda: _FakeUart())
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)
    return events, uart3, uart8


def install_fake_uart6_factory(monkeypatch, uart6: _FakeUart) -> None:
    hardware_package = sys.modules.get("hardware", ModuleType("hardware"))
    uart_bus_module = sys.modules.get(
        "hardware.uart_bus", ModuleType("hardware.uart_bus")
    )

    def create_uart6():
        return uart6

    setattr(uart_bus_module, "create_uart6", create_uart6)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)


def install_counting_uart6_factory(monkeypatch, uart6: _FakeUart, calls: list) -> None:
    hardware_package = sys.modules.get("hardware", ModuleType("hardware"))
    uart_bus_module = sys.modules.get(
        "hardware.uart_bus", ModuleType("hardware.uart_bus")
    )

    def create_uart6():
        calls.append("create_uart6")
        return uart6

    setattr(uart_bus_module, "create_uart6", create_uart6)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)


def install_fake_uart8_factory(monkeypatch, uart8: _FakeUart) -> None:
    hardware_package = sys.modules.get("hardware", ModuleType("hardware"))
    uart_bus_module = sys.modules.get(
        "hardware.uart_bus", ModuleType("hardware.uart_bus")
    )

    def create_uart8():
        return uart8

    setattr(uart_bus_module, "create_uart8", create_uart8)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)


def install_counting_uart8_factory(monkeypatch, uart8: _FakeUart, calls: list) -> None:
    hardware_package = sys.modules.get("hardware", ModuleType("hardware"))
    uart_bus_module = sys.modules.get(
        "hardware.uart_bus", ModuleType("hardware.uart_bus")
    )

    def create_uart8():
        calls.append("create_uart8")
        return uart8

    setattr(uart_bus_module, "create_uart8", create_uart8)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)
