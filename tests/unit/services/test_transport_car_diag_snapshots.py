"""TransportCar 诊断快照单元测试."""

import sys
import types
from typing import Any, Optional, cast

import pytest

from services.vision_state_machine import SMState, VisionResolvedTarget


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
            pass

        def init(self, *_args, **_kwargs):
            return None

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
from services.transport_car import TransportCar  # noqa: E402


class FakeLed:
    """LED 假对象."""

    def __init__(self):
        self.toggle_count = 0

    def toggle(self):
        self.toggle_count += 1


class FakeVisionObservation:
    """视觉观测假对象."""

    def __init__(self, x: float, y: float, timestamp_ms: int):
        self.x = x
        self.y = y
        self.timestamp_ms = timestamp_ms


class FakeVisionProtocol:
    """视觉协议假对象."""

    def __init__(self, observation: Optional[FakeVisionObservation]):
        self.observation = observation

    def get_observation(self, now_ms: int):
        return self.observation


def build_transport_car_for_diag() -> Any:
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.tick_count = 12
    car.last_loop_dt_us = 5400
    car.max_loop_dt_us = 6200
    car.loop_dt_total_us = 60000
    car.loop_overrun_count = 2
    car.boot_time_ms = 1000
    car._now_ms = lambda: 2500
    car.command_lock = True
    car.rear_only_mode = False
    car.last_exception_text = "none"
    car._yaw_rate = 12.5
    car._last_gz_raw = 345.0
    car.heading_est = 33.3
    car.imu_data = [0, 0, 0, 0, 0, 345]
    car.wheel_states = [
        {"name": "m", "raw_speed": 11.0, "filtered_speed": 9.5, "duty": 1200.0},
        {"name": "l", "raw_speed": 12.0, "filtered_speed": 10.5, "duty": 1300.0},
        {"name": "r", "raw_speed": 13.0, "filtered_speed": 11.5, "duty": 1400.0},
    ]
    car.target_speeds = {"m": 15.0, "l": 16.0, "r": 17.0}
    car.vision_state_machine = types.SimpleNamespace(state=SMState.ALIGN_DX)
    car.vision_protocol = FakeVisionProtocol(
        FakeVisionObservation(x=120.0, y=80.0, timestamp_ms=2400)
    )
    car._vision_resolved_target = VisionResolvedTarget(
        x=0.2, y=0.4, angle_deg=15.0, rear_only_mode=True
    )
    car.odometry = types.SimpleNamespace(x=1.2, y=-0.3)
    return car


def test_handle_tick_updates_runtime_statistics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.tick_count = 0
    car.led = FakeLed()
    car.last_time_us = 1000
    car.last_loop_dt_us = 0
    car.max_loop_dt_us = 0
    car.loop_dt_total_us = 0
    car.loop_overrun_count = 0
    car._refresh_vision_target = lambda: None
    car._update_wheel_speeds = lambda: None
    car._update_attitude = lambda _dt: None
    car._run_control = lambda _dt: None

    monkeypatch.setattr(
        transport_car_module.time, "ticks_us", lambda: 7005, raising=False
    )
    monkeypatch.setattr(
        transport_car_module.time,
        "ticks_diff",
        lambda current, last: current - last,
        raising=False,
    )

    car._handle_tick()

    assert car.tick_count == 1
    assert car.led.toggle_count == 1
    assert car.last_loop_dt_us == 6005
    assert car.max_loop_dt_us == 6005
    assert car.loop_dt_total_us == 6005
    assert car.loop_overrun_count == 1


def test_build_tick_snapshot_reports_overrun_statistics() -> None:
    car = build_transport_car_for_diag()

    snapshot = car.build_tick_snapshot()

    assert snapshot == {
        "count": 12,
        "last_us": 5400,
        "max_us": 6200,
        "avg_us": 5000,
        "overrun": 2,
    }


def test_build_encoder_and_motor_snapshots_report_runtime_values() -> None:
    car = build_transport_car_for_diag()

    encoder_snapshot = car.build_encoder_snapshot()
    motor_snapshot = car.build_motor_snapshot()

    assert encoder_snapshot == {
        "m_raw": 11.0,
        "m_filt": 9.5,
        "l_raw": 12.0,
        "l_filt": 10.5,
        "r_raw": 13.0,
        "r_filt": 11.5,
    }
    assert motor_snapshot == {
        "m_target": 15.0,
        "m_duty": 1200.0,
        "l_target": 16.0,
        "l_duty": 1300.0,
        "r_target": 17.0,
        "r_duty": 1400.0,
        "rear": 1,
    }


def test_build_health_imu_and_vision_snapshots_use_current_runtime_state() -> None:
    car = build_transport_car_for_diag()

    health_snapshot = car.build_health_snapshot()
    imu_snapshot = car.build_imu_snapshot()
    vision_snapshot = car.build_vision_snapshot()

    assert health_snapshot == {
        "alive": 1,
        "uptime_ms": 1500,
        "lock": 1,
        "rear": 1,
        "last_err": "none",
        "vision_state": "ALIGN_DX",
    }
    assert imu_snapshot == {
        "ok": 1,
        "yaw_deg": 33.3,
        "yaw_rate_dps": 12.5,
        "gz_raw": 345.0,
    }
    assert vision_snapshot == {
        "state": "ALIGN_DX",
        "obs_age_ms": 100,
        "obs_x": 120.0,
        "obs_y": 80.0,
        "target_x": 0.2,
        "target_y": 0.4,
        "target_angle": 15.0,
    }
