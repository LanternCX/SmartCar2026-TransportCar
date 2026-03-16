"""TransportCar 主辅车 profile 单元测试."""

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

import services.car as transport_car_module  # noqa: E402
from vision.protocol import VisionProtocol  # noqa: E402


def _patch_runtime_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_main_vehicle_profile_enables_dual_camera_polling_and_state_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime_dependencies(monkeypatch)

    car = transport_car_module.TransportCar(vehicle_role="main")

    assert car.vehicle_role == "main"
    assert car.vision_processing_enabled is True
    assert car.dual_camera_polling_enabled is True
    assert car.single_task_state_machine_enabled is True

    car.handle_uart_line("left=10,top=20,right=40,bottom=60", source="uart6")
    coordinator = cast(Any, car.vision_coordinator)
    observation = coordinator.get_observation(car.now_ms())

    assert observation is not None
    assert observation.left == 10.0
    assert observation.bottom == 60.0
    assert car.role_profile.vehicle_role == "main"
    assert car.role_profile.vision_processing_enabled is True
    assert car.role_profile.dual_camera_polling_enabled is True
    assert car.role_profile.single_task_state_machine_enabled is True


def test_aux_vehicle_profile_disables_visual_processing_and_keeps_execution_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime_dependencies(monkeypatch)

    car = transport_car_module.TransportCar(vehicle_role="aux")
    apply_calls = []
    car._ensure_uart_ingress()
    cast(Any, car.uart_ingress).apply_command = lambda line, source="uart6": (
        apply_calls.append((source, line))
    )

    car.handle_uart_line("left=10,top=20,right=40,bottom=60", source="uart6")
    car.handle_uart_line("vx=1", source="uart6")
    coordinator = cast(Any, car.vision_coordinator)

    assert car.vehicle_role == "aux"
    assert car.vision_processing_enabled is False
    assert car.dual_camera_polling_enabled is False
    assert car.single_task_state_machine_enabled is False
    assert coordinator.get_state_name() == "DISABLED"
    assert coordinator.get_observation(car.now_ms()) is None
    assert apply_calls == [("uart6", "vx=1")]
    assert car.role_profile.vehicle_role == "aux"
    assert car.role_profile.vision_processing_enabled is False


def test_aux_vehicle_profile_uses_shared_vision_reserved_payload_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime_dependencies(monkeypatch)

    car = transport_car_module.TransportCar(vehicle_role="aux")
    apply_calls = []
    car._ensure_uart_ingress()
    cast(Any, car.uart_ingress).apply_command = lambda line, source="uart6": (
        apply_calls.append((source, line))
    )

    reserved_line = "left=10,top=20,right=40,bottom=60"
    assert VisionProtocol.is_reserved_payload(reserved_line) is True

    car.handle_uart_line(reserved_line, source="uart6")

    assert apply_calls == []
