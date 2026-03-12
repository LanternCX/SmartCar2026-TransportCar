"""TransportCar 诊断快照单元测试."""

import sys
import types
from typing import Any, Optional, cast

import pytest

from services.commanding.session import CommandSession
from services.runtime.diagnostics_facade import DiagnosticsFacade
from vision.state_defs import SMState
from vision.transforms import VisionResolvedTarget


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
from services.transport_car import TransportCar  # noqa: E402


class FakeLed:
    """LED 假对象."""

    def __init__(self):
        self.toggle_count = 0

    def toggle(self):
        self.toggle_count += 1


class FakeVisionObservation:
    """视觉观测假对象."""

    def __init__(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        timestamp_ms: int,
    ):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.center_x = (left + right) / 2.0
        self.center_y = (top + bottom) / 2.0
        self.timestamp_ms = timestamp_ms


class FakeVisionProtocol:
    """视觉协议假对象."""

    def __init__(self, observation: Optional[FakeVisionObservation]):
        self.observation = observation

    def get_observation(self, now_ms: int):
        return self.observation


class FakeVisionCoordinator:
    """视觉协调器假对象."""

    def __init__(
        self,
        observation: Optional[FakeVisionObservation],
        resolved_target: Optional[VisionResolvedTarget],
        state_name: str = "ALIGN_DX",
    ):
        self.protocol = FakeVisionProtocol(observation)
        self.resolved_target = resolved_target
        self.state_name = state_name

    def get_state_name(self) -> str:
        return self.state_name

    def build_snapshot(self, now_ms: int):
        snapshot = {
            "state": self.get_state_name(),
            "obs_age_ms": None,
            "obs_left": None,
            "obs_top": None,
            "obs_right": None,
            "obs_bottom": None,
            "obs_center_x": None,
            "obs_center_y": None,
            "target_x": None,
            "target_y": None,
            "target_angle": None,
        }
        observation = self.protocol.get_observation(now_ms)
        if observation is not None:
            snapshot["obs_age_ms"] = int(now_ms) - int(observation.timestamp_ms)
            snapshot["obs_left"] = float(observation.left)
            snapshot["obs_top"] = float(observation.top)
            snapshot["obs_right"] = float(observation.right)
            snapshot["obs_bottom"] = float(observation.bottom)
            snapshot["obs_center_x"] = float(observation.center_x)
            snapshot["obs_center_y"] = float(observation.center_y)
        if self.resolved_target is not None:
            snapshot["target_x"] = float(self.resolved_target.x)
            snapshot["target_y"] = float(self.resolved_target.y)
            snapshot["target_angle"] = float(self.resolved_target.angle_deg)
        return snapshot


def build_transport_car_for_diag() -> Any:
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.tick_count = 12
    car.last_loop_dt_us = 5400
    car.max_loop_dt_us = 6200
    car.loop_dt_total_us = 60000
    car.loop_overrun_count = 2
    car.boot_time_ms = 1000
    car._now_ms = lambda: 2500
    car.now_ms = car._now_ms
    car.last_exception_text = "none"
    car._command_session = CommandSession()
    car.command_session.command_lock = True
    car.command_session.rear_only_mode = False
    wheel_states = [
        {"name": "m", "raw_speed": 11.0, "filtered_speed": 9.5, "duty": 1200.0},
        {"name": "l", "raw_speed": 12.0, "filtered_speed": 10.5, "duty": 1300.0},
        {"name": "r", "raw_speed": 13.0, "filtered_speed": 11.5, "duty": 1400.0},
    ]
    car.chassis_state = types.SimpleNamespace(
        yaw_rate=12.5,
        last_gz_raw=345.0,
        heading_est=33.3,
        imu_data=[0, 0, 0, 0, 0, 345],
        wheel_states=wheel_states,
        target_speeds={"m": 15.0, "l": 16.0, "r": 17.0},
        odometry=types.SimpleNamespace(x=1.2, y=-0.3),
    )
    car.vision_coordinator = FakeVisionCoordinator(
        FakeVisionObservation(
            left=100.0, top=20.0, right=140.0, bottom=90.0, timestamp_ms=2400
        ),
        VisionResolvedTarget(x=0.2, y=0.4, angle_deg=15.0, rear_only_mode=True),
        state_name="ALIGN_DX",
    )
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

    snapshot = car.get_diagnostics_facade().build_tick_snapshot()

    assert snapshot == {
        "count": 12,
        "last_us": 5400,
        "max_us": 6200,
        "avg_us": 5000,
        "overrun": 2,
    }


def test_build_encoder_and_motor_snapshots_report_runtime_values() -> None:
    car = build_transport_car_for_diag()

    facade = car.get_diagnostics_facade()
    encoder_snapshot = facade.build_encoder_snapshot()
    motor_snapshot = facade.build_motor_snapshot()

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

    facade = car.get_diagnostics_facade()
    health_snapshot = facade.build_health_snapshot()
    imu_snapshot = facade.build_imu_snapshot()
    vision_snapshot = facade.build_vision_snapshot()

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
        "obs_left": 100.0,
        "obs_top": 20.0,
        "obs_right": 140.0,
        "obs_bottom": 90.0,
        "obs_center_x": 120.0,
        "obs_center_y": 55.0,
        "target_x": 0.2,
        "target_y": 0.4,
        "target_angle": 15.0,
    }


def test_diagnostics_facade_preserves_snapshot_keys_and_query_format() -> None:
    car = build_transport_car_for_diag()

    facade = car.get_diagnostics_facade()

    assert facade.build_health_snapshot().keys() == {
        "alive",
        "uptime_ms",
        "lock",
        "rear",
        "last_err",
        "vision_state",
    }
    assert facade.build_tick_snapshot().keys() == {
        "count",
        "last_us",
        "max_us",
        "avg_us",
        "overrun",
    }
    assert facade.build_imu_snapshot().keys() == {
        "ok",
        "yaw_deg",
        "yaw_rate_dps",
        "gz_raw",
    }
    assert facade.build_encoder_snapshot().keys() == {
        "m_raw",
        "m_filt",
        "l_raw",
        "l_filt",
        "r_raw",
        "r_filt",
    }
    assert facade.build_motor_snapshot().keys() == {
        "m_target",
        "m_duty",
        "l_target",
        "l_duty",
        "r_target",
        "r_duty",
        "rear",
    }
    assert facade.build_vision_snapshot().keys() == {
        "state",
        "obs_age_ms",
        "obs_left",
        "obs_top",
        "obs_right",
        "obs_bottom",
        "obs_center_x",
        "obs_center_y",
        "target_x",
        "target_y",
        "target_angle",
    }


def test_transport_car_no_longer_exposes_diag_snapshot_wrappers() -> None:
    assert hasattr(TransportCar, "build_health_snapshot") is False
    assert hasattr(TransportCar, "build_tick_snapshot") is False
    assert hasattr(TransportCar, "build_imu_snapshot") is False
    assert hasattr(TransportCar, "build_encoder_snapshot") is False
    assert hasattr(TransportCar, "build_motor_snapshot") is False
    assert hasattr(TransportCar, "build_vision_snapshot") is False


def test_diagnostics_facade_builds_snapshots_from_runtime_public_state() -> None:
    runtime = types.SimpleNamespace(
        boot_time_ms=1000,
        now_ms=lambda: 2500,
        command_session=CommandSession(),
        last_exception_text="none",
        tick_count=12,
        last_loop_dt_us=5400,
        max_loop_dt_us=6200,
        loop_dt_total_us=60000,
        loop_overrun_count=2,
        logger_manager=types.SimpleNamespace(
            filter_modules=[],
            profile_name="DEFAULT",
            level_name="INFO",
            filter_mode="allow",
            color_enabled=False,
        ),
        vision_coordinator=FakeVisionCoordinator(
            FakeVisionObservation(
                left=100.0,
                top=20.0,
                right=140.0,
                bottom=90.0,
                timestamp_ms=2400,
            ),
            VisionResolvedTarget(x=0.2, y=0.4, angle_deg=15.0, rear_only_mode=True),
            state_name="ALIGN_DX",
        ),
        chassis_state=types.SimpleNamespace(
            yaw_rate=12.5,
            last_gz_raw=345.0,
            heading_est=33.3,
            imu_data=[0, 0, 0, 0, 0, 345],
            wheel_states=[
                {"name": "m", "raw_speed": 11.0, "filtered_speed": 9.5, "duty": 1200.0},
                {
                    "name": "l",
                    "raw_speed": 12.0,
                    "filtered_speed": 10.5,
                    "duty": 1300.0,
                },
                {
                    "name": "r",
                    "raw_speed": 13.0,
                    "filtered_speed": 11.5,
                    "duty": 1400.0,
                },
            ],
            target_speeds={"m": 15.0, "l": 16.0, "r": 17.0},
            odometry=types.SimpleNamespace(x=1.2, y=-0.3),
        ),
    )
    runtime.command_session.command_lock = True
    runtime.command_session.rear_only_mode = False

    facade = DiagnosticsFacade(runtime)

    assert facade.build_health_snapshot() == {
        "alive": 1,
        "uptime_ms": 1500,
        "lock": 1,
        "rear": 1,
        "last_err": "none",
        "vision_state": "ALIGN_DX",
    }
    assert facade.build_tick_snapshot() == {
        "count": 12,
        "last_us": 5400,
        "max_us": 6200,
        "avg_us": 5000,
        "overrun": 2,
    }
    assert facade.build_imu_snapshot() == {
        "ok": 1,
        "yaw_deg": 33.3,
        "yaw_rate_dps": 12.5,
        "gz_raw": 345.0,
    }
    assert facade.build_encoder_snapshot() == {
        "m_raw": 11.0,
        "m_filt": 9.5,
        "l_raw": 12.0,
        "l_filt": 10.5,
        "r_raw": 13.0,
        "r_filt": 11.5,
    }
    assert facade.build_motor_snapshot() == {
        "m_target": 15.0,
        "m_duty": 1200.0,
        "l_target": 16.0,
        "l_duty": 1300.0,
        "r_target": 17.0,
        "r_duty": 1400.0,
        "rear": 1,
    }
    assert facade.build_vision_snapshot() == {
        "state": "ALIGN_DX",
        "obs_age_ms": 100,
        "obs_left": 100.0,
        "obs_top": 20.0,
        "obs_right": 140.0,
        "obs_bottom": 90.0,
        "obs_center_x": 120.0,
        "obs_center_y": 55.0,
        "target_x": 0.2,
        "target_y": 0.4,
        "target_angle": 15.0,
    }


def test_diagnostics_facade_requires_public_runtime_interfaces() -> None:
    runtime = types.SimpleNamespace(
        boot_time_ms=1000,
        now_ms=lambda: 2500,
        command_session=CommandSession(),
        last_exception_text="none",
        tick_count=0,
        last_loop_dt_us=0,
        max_loop_dt_us=0,
        loop_dt_total_us=0,
        loop_overrun_count=0,
        logger_manager=types.SimpleNamespace(
            filter_modules=[],
            profile_name="DEFAULT",
            level_name="INFO",
            filter_mode="allow",
            color_enabled=False,
        ),
        vision_coordinator=FakeVisionCoordinator(None, None, state_name="UNKNOWN"),
        chassis_state=types.SimpleNamespace(
            heading_est=0.0,
            imu_data=[1],
            wheel_states=[],
            target_speeds={},
            odometry=types.SimpleNamespace(x=0.0, y=0.0),
        ),
    )

    facade = DiagnosticsFacade(runtime)

    assert facade.build_health_snapshot()["uptime_ms"] == 1500
    assert facade.build_imu_snapshot() == {
        "ok": 1,
        "yaw_deg": 0.0,
        "yaw_rate_dps": 0.0,
        "gz_raw": 0.0,
    }


def test_diagnostics_facade_requires_command_session_and_chassis_state_owners() -> None:
    runtime = types.SimpleNamespace(
        boot_time_ms=1000,
        now_ms=lambda: 2500,
        last_exception_text="none",
        tick_count=0,
        last_loop_dt_us=0,
        max_loop_dt_us=0,
        loop_dt_total_us=0,
        loop_overrun_count=0,
        logger_manager=types.SimpleNamespace(
            filter_modules=[],
            profile_name="DEFAULT",
            level_name="INFO",
            filter_mode="allow",
            color_enabled=False,
        ),
        vision_coordinator=FakeVisionCoordinator(None, None, state_name="UNKNOWN"),
    )

    facade = DiagnosticsFacade(runtime)

    with pytest.raises(AttributeError):
        facade.build_health_snapshot()
    with pytest.raises(AttributeError):
        facade.build_pos_snapshot()
