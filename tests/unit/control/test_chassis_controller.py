"""ChassisController 单元测试."""

import types

import pytest

from control.chassis_controller import ChassisController
from control.chassis_state import ChassisState


pytestmark = pytest.mark.unit


class FakeMotor:
    """测试电机假对象."""

    def __init__(self):
        self.values = []

    def duty(self, value):
        self.values.append(value)


class FakeController:
    """测试速度环假对象."""

    def __init__(self):
        self.calls = []
        self.reset_called = False

    def update(self, target, now, dt_s):
        self.calls.append((target, now, dt_s))
        return target - now

    def reset(self):
        self.reset_called = True


class FakeFilter:
    """返回输入值的滤波器假对象."""

    def update(self, value):
        return value


class FakeYawPid:
    """测试偏航 PID 假对象."""

    def __init__(self):
        self.calls = []
        self.integral = 0.0
        self.reset_called = False

    def update(self, target, now, dt_s):
        self.calls.append((target, now, dt_s))
        return target - now

    def reset(self):
        self.reset_called = True
        self.integral = 0.0


class FakeWheelSpeedController:
    """记录调用顺序的轮速控制假对象."""

    def __init__(self, order):
        self.order = order

    def update_wheel_speeds(self, wheel_states):
        self.order.append("wheels")

    def apply_target_speeds(
        self,
        wheel_states,
        target_speeds,
        target_vx_cmd,
        target_vy_cmd,
        omega_cmd,
        dt_s,
        rear_only_mode,
    ):
        self.order.append("apply")
        target_speeds["m"] = 11.0
        target_speeds["l"] = 0.0
        target_speeds["r"] = 0.0


class FakeAttitudeEstimator:
    """记录调用顺序的姿态估计假对象."""

    def __init__(self, order):
        self.order = order

    def update_attitude(self, state, dt_s):
        self.order.append("attitude")


class FakeMotionPlanner:
    """记录调用顺序的规划器假对象."""

    def __init__(self, order):
        self.order = order

    def compute_omega_cmd(self, state, dt_s, cmd_angle, cmd_omega):
        self.order.append("omega")
        return 5.0

    def compute_planar_targets(
        self,
        dt_s,
        heading_est_deg,
        odometry,
        last_cmd,
        active_target_x,
        active_target_y,
    ):
        self.order.append("planar")
        return (2.0, 3.0)

    def compute_angle_error_deg(self, target_angle, current_angle):
        return float(target_angle) - float(current_angle)


def _build_wheel_state(name):
    return {
        "name": name,
        "encoder": types.SimpleNamespace(get=lambda: 0.0),
        "input_lpf": FakeFilter(),
        "diff_filter": FakeFilter(),
        "dual_filter": types.SimpleNamespace(update=lambda value: (value, 0.0, 0.0)),
        "output_lpf": FakeFilter(),
        "controller": FakeController(),
        "motor": FakeMotor(),
        "filtered_speed": 0.0,
        "duty": 0.0,
    }


def test_chassis_controller_preserves_tick_order_and_updates_outputs() -> None:
    order = []
    state = ChassisState(
        wheel_states=[
            _build_wheel_state("m"),
            _build_wheel_state("l"),
            _build_wheel_state("r"),
        ],
        target_speeds={"m": 0.0, "l": 0.0, "r": 0.0},
        yaw_pid=FakeYawPid(),
        heading_est=270.0,
        heading_target=0.0,
        yaw_integral=0.0,
        odometry=types.SimpleNamespace(x=0.0, y=0.0),
    )
    controller = ChassisController(
        state=state,
        wheel_speed_controller=FakeWheelSpeedController(order),
        attitude_estimator=FakeAttitudeEstimator(order),
        motion_planner=FakeMotionPlanner(order),
    )

    controller.tick(
        dt_s=0.01,
        active_target_x=None,
        active_target_y=None,
        active_angle=-90.0,
        cmd_omega=None,
        active_rear_only_mode=True,
        last_cmd={"angle": -90.0},
        command_lock=True,
        rear_only_mode=True,
    )

    assert order == ["wheels", "attitude", "omega", "planar", "apply"]
    assert controller.state.target_speeds["m"] == 11.0


def test_chassis_state_does_not_keep_command_session_fields() -> None:
    state = ChassisState()

    assert hasattr(state, "last_cmd") is False
    assert hasattr(state, "command_lock") is False
    assert hasattr(state, "rear_only_mode") is False
