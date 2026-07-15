"""transport runtime 测试辅助.

@file tests/unit/runtime/transport_runtime_support.py
"""

from importlib import import_module
import math
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
        "role.master",
        "role.master.forward_runtime",
        "role.assistant",
        "role.assistant.follow_runtime",
        "config",
        "config.motion",
        "config.vision",
        "utils.startup_log",
        module_name,
    ):
        sys.modules.pop(loaded_name, None)
    module = import_module(module_name)
    if module_name == "role.master.forward_runtime":
        runtime_type = module.MasterForwardRuntime

        def _master_runtime_factory(*args, **kwargs):
            kwargs.setdefault(
                "obstacle_slots",
                ((None, -1.0, -1.0),) * 3,
            )
            return runtime_type(*args, **kwargs)

        setattr(module, "MasterForwardRuntime", _master_runtime_factory)
    if module_name == "role.assistant.follow_runtime":
        runtime_type = module.AssistantFollowRuntime

        def _assistant_runtime_factory(*args, **kwargs):
            kwargs.setdefault(
                "obstacle_slots",
                ((None, -1.0, -1.0),) * 3,
            )
            return runtime_type(*args, **kwargs)

        setattr(module, "AssistantFollowRuntime", _assistant_runtime_factory)
    return module


def install_fake_core(monkeypatch):
    cars = []
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")

    class _FakeOdometry:
        def __init__(self) -> None:
            self.x = 0.0
            self.y = 0.0

    class FakeTransportCar:
        def __init__(self, vehicle_role=None) -> None:
            self.vehicle_role = vehicle_role
            self.odometry = _FakeOdometry()
            self.wheel_encoders = ("enc-m", "enc-l", "enc-r")
            self.w_filt = [0.0, 0.0, 0.0]
            self.imu = "imu"
            self.heading_est = 0.0
            self.command_lock = False
            self.orbit_mode = False
            self.control_vx = 0.0
            self.control_vy = 0.0
            self.control_omega = 0.0
            self.control_omega_active = True
            self.control_x = 0.0
            self.control_y = 0.0
            self.control_angle = 0.0
            self.control_x_active = False
            self.control_y_active = False
            self.control_angle_active = False
            self.last_chassis_target = {
                "source": None,
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "has_omega": False,
            }
            self.last_exception_text = "none"
            self.position_integration_enabled = True
            self.grayscale_edges = []
            self.events = []
            cars.append(self)

        def read_grayscale_edge(self) -> int:
            if self.grayscale_edges:
                return int(self.grayscale_edges.pop(0))
            return 0

        def mark_tick(self, tick=None) -> None:
            self.events.append(("mark_tick", tick))

        def set_ticker(self, ticker_obj) -> None:
            self.events.append(("set_ticker", ticker_obj))

        def step(self) -> bool:
            self.events.append("transport_step")
            return False

        def wheel_stop_confirmed(self, threshold) -> bool:
            threshold = float(threshold)
            return (
                abs(float(self.w_filt[0])) <= threshold
                and abs(float(self.w_filt[1])) <= threshold
                and abs(float(self.w_filt[2])) <= threshold
            )

        def handle_velocity_packet(self, vx, vy, omega, source, has_omega=True) -> None:
            self.events.append(("handle_velocity", source, float(vx), float(vy), float(omega)))
            self.control_vx = float(vx)
            self.control_vy = float(vy)
            self.control_omega = float(omega)
            self.control_omega_active = True
            self.control_x_active = False
            self.control_y_active = False
            self.control_angle_active = False
            self.last_chassis_target = {
                "source": source,
                "vx": float(vx),
                "vy": float(vy),
                "omega": float(omega),
                "has_omega": bool(has_omega),
            }
            self.command_lock = False

        def set_orbit_target(self, target_angle_deg, radius_scale, direction=0) -> None:
            event = ["set_orbit_target", float(target_angle_deg), float(radius_scale)]
            if int(direction):
                event.append(int(direction))
            self.events.append(tuple(event))
            self.command_lock = True
            self.orbit_mode = True
            self.control_vx = 0.0
            self.control_vy = 0.0
            self.control_omega = 0.0
            self.control_omega_active = True
            self.control_angle = float(target_angle_deg)
            self.control_angle_active = True

        def set_orbit_velocity_correction(self, vx, vy) -> None:
            self.events.append(("set_orbit_velocity_correction", float(vx), float(vy)))
            self.control_vx = float(vx)
            self.control_vy = float(vy)

        def set_position_integration_enabled(self, enabled) -> None:
            self.position_integration_enabled = bool(enabled)
            self.events.append(
                ("set_position_integration_enabled", bool(enabled))
            )

        def apply_forward_pose_distance(self, distance_m, heading_deg) -> None:
            heading_rad = math.radians(float(heading_deg))
            distance_m = float(distance_m)
            self.odometry.x += distance_m * math.sin(heading_rad)
            self.odometry.y += distance_m * math.cos(heading_rad)
            self.events.append(
                (
                    "apply_forward_pose_distance",
                    distance_m,
                    float(heading_deg),
                )
            )

        def set_heading_target(self, angle_deg) -> None:
            self.events.append(("set_heading_target", float(angle_deg)))
            self.command_lock = True
            self.control_angle = float(angle_deg)
            self.control_angle_active = True

        def set_heading_transition_target(self, angle_deg) -> None:
            self.events.append(("set_heading_transition_target", float(angle_deg)))
            self.command_lock = True
            self.control_angle = float(angle_deg)
            self.control_angle_active = True

        def set_translation_target(
            self,
            x,
            y,
            hold_heading_deg=None,
            max_speed_cmd=None,
        ) -> None:
            event = ["set_translation_target", float(x), float(y)]
            if hold_heading_deg is not None:
                event.append(float(hold_heading_deg))
            if max_speed_cmd is not None:
                event.append(float(max_speed_cmd))
            self.events.append(tuple(event))
            self.command_lock = True
            self.control_x = float(x)
            self.control_y = float(y)
            self.control_x_active = True
            self.control_y_active = True

        def set_relative_translation_target(self, dx, dy, hold_heading_deg=None, max_speed_cmd=None) -> None:
            event = ["set_relative_translation_target", float(dx), float(dy)]
            if hold_heading_deg is not None:
                event.append(float(hold_heading_deg))
            if max_speed_cmd is not None:
                event.append(float(max_speed_cmd))
            self.events.append(tuple(event))
            self.command_lock = True
            self.control_vx = 0.0
            self.control_vy = 0.0
            self.control_omega = 0.0
            self.control_omega_active = True
            self.control_x = float(dx)
            self.control_y = float(dy)
            self.control_x_active = True
            self.control_y_active = True

        @property
        def control_state(self):
            snapshot = {
                "vx": float(self.control_vx),
                "vy": float(self.control_vy),
            }
            if self.control_omega_active:
                snapshot["omega"] = float(self.control_omega)
            if self.control_x_active:
                snapshot["x"] = float(self.control_x)
            if self.control_y_active:
                snapshot["y"] = float(self.control_y)
            if self.control_angle_active:
                snapshot["angle"] = float(self.control_angle)
            return snapshot

        def calibrate_pose_to_field_edge(self, edge, heading_deg, inset_m) -> None:
            self.events.append(
                (
                    "calibrate_pose_to_field_edge",
                    str(edge),
                    float(heading_deg),
                    float(inset_m),
                )
            )

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
