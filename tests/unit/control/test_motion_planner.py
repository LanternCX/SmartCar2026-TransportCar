"""MotionPlanner 单元测试."""

import pytest

from control.motion_planner import MotionPlanner


pytestmark = pytest.mark.unit


class FakeKinematics:
    """测试用运动学假对象."""

    def velocity_m_s_to_pulses(self, value, dt_s):
        return value


class FakeOdometry:
    """测试用里程计假对象."""

    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y


def test_motion_planner_preserves_position_and_velocity_mode_semantics() -> None:
    planner = MotionPlanner(kinematics=FakeKinematics())
    odometry = FakeOdometry(x=1.0, y=1.0)
    last_cmd = {"vx": 7.5, "vy": -2.5, "x": 100.0, "y": 100.0}

    target_vx_cmd, target_vy_cmd = planner.compute_planar_targets(
        dt_s=0.01,
        heading_est_deg=0.0,
        odometry=odometry,
        last_cmd=last_cmd,
        active_target_x=2.0,
        active_target_y=1.0,
    )

    assert target_vx_cmd != 0.0
    assert target_vy_cmd == 0.0
    assert abs(target_vx_cmd) < 1000.0

    velocity_vx_cmd, velocity_vy_cmd = planner.compute_planar_targets(
        dt_s=0.01,
        heading_est_deg=0.0,
        odometry=odometry,
        last_cmd=last_cmd,
        active_target_x=None,
        active_target_y=None,
    )

    assert velocity_vx_cmd == 7.5
    assert velocity_vy_cmd == -2.5
