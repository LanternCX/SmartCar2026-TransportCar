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
        self.read_error: Optional[BaseException] = None

    def any(self) -> int:
        return len(self._buffer)

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
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
            self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            self.rear_only_mode = False
            self.command_lock = False
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
            events.append("transport_step")
            return False

        def _handle_uart_line(self, line: str, source: str) -> None:
            events.append(("handle_uart_line", source, line))
            dispatched = set()
            for fragment in line.split(","):
                item = fragment.strip()
                if not item or "=" not in item:
                    continue
                key, value_text = item.split("=", 1)
                key = key.strip()
                value_text = value_text.strip()
                if key in ("vx", "vy", "omega"):
                    self.last_cmd[key] = float(value_text)
                    dispatched.add(key)
                if key in ("x", "y", "angle"):
                    self.last_cmd[key] = float(value_text)
                    dispatched.add(key)
                if key in ("x", "y"):
                    self.last_cmd.pop("vx", None)
                    self.last_cmd.pop("vy", None)
                if key == "angle":
                    self.last_cmd.pop("omega", None)
                if key == "rear":
                    self.rear_only_mode = value_text == "1"
                    self.command_lock = self.rear_only_mode
                    self.command_mode = "locked" if self.rear_only_mode else "none"
                    dispatched.add(key)
            if dispatched:
                self._finalize_route(dispatched)

        def _finalize_route(self, dispatched) -> None:
            events.append(("finalize_route", tuple(sorted(dispatched))))
            if "vx" in dispatched or "vy" in dispatched:
                self.last_cmd.pop("x", None)
                self.last_cmd.pop("y", None)
            if "omega" in dispatched:
                self.last_cmd.pop("angle", None)

            active_pose_target = self._has_active_pose_target()
            if not active_pose_target:
                self.command_lock = False
                self.command_mode = "none"

        def _has_active_translation_target(self) -> bool:
            return self.last_cmd.get("x") is not None or self.last_cmd.get("y") is not None

        def _has_active_rotation_target(self) -> bool:
            return self.last_cmd.get("angle") is not None

        def _has_active_pose_target(self) -> bool:
            return self._has_active_translation_target() or self._has_active_rotation_target()

        def build_health_snapshot(self) -> dict:
            return {"alive": 1, "last_err": "none"}

        def get_query_uart(self):
            return self.uart3

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
