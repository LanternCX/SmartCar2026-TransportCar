"""MinimalDiagnostics 单元测试."""

import sys
import types
from typing import Any, cast

import pytest

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


def _build_logger_manager_stub():
    return types.SimpleNamespace(
        filter_modules=[],
        profile_name="RUN",
        level_name="INFO",
        filter_mode="off",
        color_enabled=False,
    )


def test_minimal_diagnostics_reads_core_without_copying_state() -> None:
    from services.runtime.minimal_diagnostics import MinimalDiagnostics

    core = types.SimpleNamespace(
        boot_time_ms=1000,
        oom_count=1,
        last_oom_stage="format",
        last_exception_text="none",
        tick_count=10,
        last_loop_dt_us=5000,
        max_loop_dt_us=7000,
        loop_dt_total_us=50000,
        loop_overrun_count=1,
        logger_manager=_build_logger_manager_stub(),
        now_ms=lambda: 2500,
    )
    command_owner = types.SimpleNamespace(command_session=CommandSession())
    motion_owner = types.SimpleNamespace(
        chassis_state=types.SimpleNamespace(
            heading_est=0.0,
            imu_data=[0.0] * 6,
            wheel_states=[],
            target_speeds={},
            odometry=types.SimpleNamespace(x=0.0, y=0.0),
        )
    )
    vision_owner = types.SimpleNamespace(
        vision_runtime=types.SimpleNamespace(
            latest_observation=None,
            selected_input=None,
            resolved_target=None,
        ),
        vision_coordinator=types.SimpleNamespace(get_state_name=lambda: "ALIGN_DX"),
    )
    diagnostics = MinimalDiagnostics(
        core=core,
        command_owner=command_owner,
        motion_owner=motion_owner,
        vision_owner=vision_owner,
    )

    first_snapshot = diagnostics.build_health_snapshot()
    core.oom_count = 3
    second_snapshot = diagnostics.build_health_snapshot()

    assert first_snapshot["oom_count"] == 1
    assert second_snapshot["oom_count"] == 3
    assert second_snapshot["vision_state"] == "ALIGN_DX"


def test_transport_car_builds_minimal_diagnostics_from_runtime_owners() -> None:
    from services.runtime.minimal_diagnostics import MinimalDiagnostics
    from services.car import TransportCar

    car = cast(Any, TransportCar.__new__(TransportCar))
    car.runtime_core = types.SimpleNamespace(
        boot_time_ms=1000,
        oom_count=2,
        last_oom_stage="format",
        last_exception_text="none",
        tick_count=5,
        last_loop_dt_us=5000,
        max_loop_dt_us=7000,
        loop_dt_total_us=25000,
        loop_overrun_count=0,
        logger_manager=_build_logger_manager_stub(),
        now_ms=lambda: 2500,
    )
    car._command_session = CommandSession()
    car._chassis_state = types.SimpleNamespace(
        heading_est=0.0,
        imu_data=[0.0] * 6,
        wheel_states=[],
        target_speeds={},
        odometry=types.SimpleNamespace(x=0.0, y=0.0),
    )
    car.vision_runtime = types.SimpleNamespace(
        latest_observation=None,
        selected_input=None,
        resolved_target=None,
    )
    car.vision_coordinator = types.SimpleNamespace(get_state_name=lambda: "DISABLED")

    facade = car.get_diagnostics_facade()

    assert isinstance(facade, MinimalDiagnostics)
    assert facade.build_health_snapshot()["oom_count"] == 2
