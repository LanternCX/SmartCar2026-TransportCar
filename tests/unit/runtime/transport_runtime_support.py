"""transport runtime 测试辅助.

@file tests/unit/runtime/transport_runtime_support.py
"""

from importlib import import_module
from pathlib import Path
from types import ModuleType
import sys

from protocol.frame import decode_frame, encode_frame


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


class ManualClock:
    def __init__(self, value: int = 0) -> None:
        self.value = int(value)

    def advance(self, delta: int) -> None:
        self.value += int(delta)

    def __call__(self) -> int:
        return int(self.value)


class BufferedUart:
    def __init__(self, incoming=b"") -> None:
        self._incoming = bytearray(incoming)
        self.messages = []
        self.any_calls = 0
        self.read_calls = 0
        self.write_calls = 0

    def any(self) -> int:
        self.any_calls += 1
        return len(self._incoming)

    def read(self, size: int) -> bytes:
        self.read_calls += 1
        chunk = bytes(self._incoming[:size])
        del self._incoming[:size]
        return chunk

    def write(self, data) -> int:
        self.write_calls += 1
        payload = bytes(data)
        self.messages.append(payload)
        return len(payload)

    def push(self, data: bytes) -> None:
        self._incoming.extend(data)


class LinkedUart(BufferedUart):
    def __init__(self) -> None:
        super().__init__()
        self.peer = None

    def write(self, data) -> int:
        payload = bytes(data)
        self.messages.append(payload)
        self.write_calls += 1
        if self.peer is not None:
            self.peer.push(payload)
        return len(payload)


def make_linked_uart_pair():
    left = LinkedUart()
    right = LinkedUart()
    left.peer = right  # pyright: ignore[reportAttributeAccessIssue]
    right.peer = left  # pyright: ignore[reportAttributeAccessIssue]
    return left, right


def import_module_clean(module_name: str, monkeypatch):
    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for loaded_name in (
        "vision.master",
        "vision.master.forward_runtime",
        "vision.assistant",
        "vision.assistant.follow_runtime",
        module_name,
    ):
        sys.modules.pop(loaded_name, None)
    return import_module(module_name)


def install_fake_core(monkeypatch):
    cars = []
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")

    class FakeTransportCar:
        def __init__(self) -> None:
            self.wheel_states = [
                {"encoder": "enc-m", "filtered_speed": 0.0},
                {"encoder": "enc-l", "filtered_speed": 0.0},
                {"encoder": "enc-r", "filtered_speed": 0.0},
            ]
            self.imu = "imu"
            self.heading_est = 0.0
            self.command_lock = False
            self.orbit_mode = False
            self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            self.last_chassis_target = {
                "source": None,
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "has_omega": False,
            }
            self.last_exception_text = "none"
            self.events = []
            cars.append(self)

        def mark_tick(self, tick=None) -> None:
            self.events.append(("mark_tick", tick))

        def set_ticker(self, ticker_obj) -> None:
            self.events.append(("set_ticker", ticker_obj))

        def step(self) -> bool:
            self.events.append("transport_step")
            return False

        def handle_velocity_packet(self, vx, vy, omega, source, has_omega=True) -> None:
            self.events.append(("handle_velocity", source, float(vx), float(vy), float(omega)))
            self.control_state = {"vx": float(vx), "vy": float(vy), "omega": float(omega)}
            self.last_chassis_target = {
                "source": source,
                "vx": float(vx),
                "vy": float(vy),
                "omega": float(omega),
                "has_omega": bool(has_omega),
            }
            self.command_lock = False

        def set_orbit_target(self, target_angle_deg, radius_scale) -> None:
            self.events.append(("set_orbit_target", float(target_angle_deg), float(radius_scale)))
            self.command_lock = True
            self.orbit_mode = True
            self.control_state = {
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "angle": float(target_angle_deg),
            }

        def set_orbit_velocity_correction(self, vx, vy) -> None:
            self.events.append(("set_orbit_velocity_correction", float(vx), float(vy)))
            self.control_state["vx"] = float(vx)
            self.control_state["vy"] = float(vy)

        def set_heading_target(self, angle_deg) -> None:
            self.events.append(("set_heading_target", float(angle_deg)))
            self.command_lock = True
            self.control_state["angle"] = float(angle_deg)

        def set_heading_transition_target(self, angle_deg) -> None:
            self.events.append(("set_heading_transition_target", float(angle_deg)))
            self.command_lock = True
            self.control_state["angle"] = float(angle_deg)

        def set_relative_translation_target(self, dx, dy, hold_heading_deg=None, max_speed_cmd=None) -> None:
            event = ["set_relative_translation_target", float(dx), float(dy)]
            if hold_heading_deg is not None:
                event.append(float(hold_heading_deg))
            if max_speed_cmd is not None:
                event.append(float(max_speed_cmd))
            self.events.append(tuple(event))
            self.command_lock = True
            self.control_state = {
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "x": float(dx),
                "y": float(dy),
            }

    monkeypatch.setitem(sys.modules, "core", core_package)
    setattr(core_module, "TransportCar", FakeTransportCar)
    monkeypatch.setitem(sys.modules, "core.runtime", core_module)
    return cars


def install_fake_uart_bus(monkeypatch, uart6, uart8):
    hardware_package = ModuleType("hardware")
    uart_bus_module = ModuleType("hardware.uart_bus")
    setattr(uart_bus_module, "create_uart6", lambda: uart6)
    setattr(uart_bus_module, "create_uart8", lambda: uart8)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)


def run_runtime_cycle(runtime):
    runtime.poll_transport_rx()
    keep_running = runtime.step()
    runtime.poll_transport_tx()
    return keep_running


def ack_last_frame(uart):
    frame = decode_frame(uart.messages[-1])
    assert frame is not None
    return encode_frame(0x03, frame["topic"], frame["seq"], b"")
