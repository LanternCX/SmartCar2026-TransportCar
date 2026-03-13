"""搬运车运行时协议契约测试."""

import sys
import time
import types
from typing import Any, cast

import pytest

from diagnostics.manager import LogManager
from diagnostics.sink import UartSink
from control.chassis_state import ChassisState
from services.commanding.session import CommandSession
from services.commanding.router import router as command_router
from vision.coordinator import VisionCoordinator
from vision.protocol import VisionProtocol


pytestmark = pytest.mark.contract


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

from services.transport_car import TransportCar  # noqa: E402


class FakeUART:
    """用于记录串口输出的假对象."""

    def __init__(self) -> None:
        self.messages = []

    def write(self, text: str) -> None:
        self.messages.append(text)

    def any(self) -> int:
        return 0

    def read(self, _size: int):
        return b""


class FakeVisionMachine:
    """用于隔离视觉状态机副作用的假对象."""

    def __init__(self) -> None:
        self.reset_called = False

    def step(self, _inputs):
        raise AssertionError("本测试不应推进真实视觉状态机")

    def reset(self) -> None:
        self.reset_called = True


class FakeOdometry:
    """最小里程计桩对象."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y

    def reset(self) -> None:
        self.x = 0.0
        self.y = 0.0


class FakeLowPassFilter:
    """用于 reset 测试的最小低通桩对象."""

    def reset(self, _value: float) -> None:
        return None


class FakeQuaternion:
    """用于 reset 测试的最小四元数桩对象."""

    def __init__(self) -> None:
        self.w = 0.0
        self.x = 1.0
        self.y = 2.0
        self.z = 3.0


class FakeKinematics:
    """用于位置控制测试的最小运动学桩对象."""

    def velocity_m_s_to_pulses(self, value: float, _dt_s: float) -> float:
        return value


def build_runtime_car():
    """构造运行时协议测试使用的最小搬运车实例."""
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.uart3 = FakeUART()
    car.uart6 = FakeUART()
    car.logger_manager = LogManager(sinks=[UartSink(cast(Any, car.uart3))])
    car.log_command = car.logger_manager.get_logger("services.command")
    car.log_vision = car.logger_manager.get_logger("vision.state")
    car.log_health = car.logger_manager.get_logger("system.health")
    car._router = command_router
    car.vision_coordinator = VisionCoordinator(
        protocol=VisionProtocol(timeout_ms=200),
        state_machine=FakeVisionMachine(),
    )
    car._command_session = CommandSession()
    car.command_session.command_lock = False
    car.command_session.lock_start_time = 0
    car.command_session.rear_only_mode = False
    car.command_session.last_rear_mode = False
    car.command_session.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    car.boot_time_ms = 0
    car.last_exception_text = "none"

    class FakeYawPid:
        def __init__(self) -> None:
            self.reset_called = False
            self.integral = 0.0

        def reset(self) -> None:
            self.reset_called = True

    car.chassis_state = ChassisState(
        heading_est=0.0,
        heading_target=0.0,
        odometry=FakeOdometry(),
        kinematics=FakeKinematics(),
        yaw_pid=FakeYawPid(),
        yaw_integral=0.0,
        yaw_rate=0.0,
        q_est=FakeQuaternion(),
        last_yaw_rad=0.0,
        gyro_lpf=FakeLowPassFilter(),
        target_speeds={"m": 0.0, "l": 0.0, "r": 0.0},
        wheel_states=[],
    )
    car._now_ms = lambda: 1000
    car._now_us = lambda: 1000000
    car._ticks_diff_us = lambda current, previous: current - previous
    car._inverse_kinematics = lambda vx, vy, omega: (vx, vy, omega)
    car.inverse_kinematics = lambda vx, vy, omega: (vx, vy, omega)
    if not hasattr(time, "ticks_ms"):
        setattr(time, "ticks_ms", lambda: 1000)
    return car


def test_uart6_visual_frame_is_consumed_before_command_routing() -> None:
    car = build_runtime_car()
    routed = []
    car.apply_command = lambda line: routed.append(line)

    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    observation = car.vision_coordinator.protocol.get_observation(now_ms=1000)
    assert observation is not None
    assert observation.center_x == 120.0
    assert routed == []


def test_query_replies_to_original_uart_source() -> None:
    car = build_runtime_car()
    car.command_session.command_lock = True

    car._handle_uart_line("?lock", source="uart3")
    car._handle_uart_line("?lock", source="uart6")

    assert car.uart3.messages == ["?lock=1\r\n"]
    assert car.uart6.messages == ["?lock=1\r\n"]


def test_rear_mode_change_locks_and_auto_reverts_after_completion() -> None:
    car = build_runtime_car()
    car.command_session.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}

    car.apply_command("rear=1,x=0,y=0,angle=0")

    assert car.command_session.command_lock is True
    assert car.command_session.rear_only_mode is True

    car._check_unlock()

    assert car.command_session.command_lock is False
    assert car.command_session.rear_only_mode is False
    assert car.command_session.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert car.uart3.messages[-1].startswith("Target Reached. Auto-revert Rear Mode")


def test_bare_reset_and_uppercase_reset_bypass_command_lock() -> None:
    car = build_runtime_car()
    car.command_session.command_lock = True
    car.command_session.rear_only_mode = True
    car.command_session.last_cmd = {"x": 1.0, "y": 2.0, "angle": 30.0}

    car.apply_command(" RESET ")

    assert car.command_session.command_lock is False
    assert car.command_session.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert car.command_session.rear_only_mode is False


def test_transport_car_runtime_surface_no_longer_exposes_compatibility_properties() -> (
    None
):
    assert hasattr(TransportCar, "last_cmd") is False
    assert hasattr(TransportCar, "command_lock") is False
    assert hasattr(TransportCar, "rear_only_mode") is False
    assert hasattr(TransportCar, "heading_est") is False
    assert hasattr(TransportCar, "build_health_snapshot") is False
