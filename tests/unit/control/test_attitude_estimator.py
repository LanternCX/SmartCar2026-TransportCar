"""AttitudeEstimator 单元测试."""

import math
import types

import pytest

from control.attitude_estimator import AttitudeEstimator
from control.chassis_state import ChassisState


pytestmark = pytest.mark.unit


class FakeQuaternion:
    """测试四元数假对象."""

    def __init__(self, yaw_rad):
        self.yaw_rad = yaw_rad
        self.calls = []

    def update(self, gx, gy, gz, dt_s):
        self.calls.append((gx, gy, gz, dt_s))

    def to_euler_yaw(self):
        return self.yaw_rad


class FakeGyroLpf:
    """测试低通假对象."""

    def __init__(self):
        self.values = []

    def update(self, value):
        self.values.append(value)
        return value + 1.0


class FakeOdometry:
    """测试里程计假对象."""

    def __init__(self):
        self.calls = []

    def update(self, vx_robot, vy_robot, theta_rad, dt):
        self.calls.append((vx_robot, vy_robot, theta_rad, dt))


class FakeKinematics:
    """测试运动学假对象."""

    def velocity_pulses_to_m_s(self, value, dt_s):
        return value * 0.1

    def forward_kinematics(self, vm, vl, vr):
        return (vm + 1.0, vl + 2.0, vr + 3.0)


def test_attitude_estimator_preserves_odometry_before_heading_update_order() -> None:
    estimator = AttitudeEstimator()
    odometry = FakeOdometry()
    quaternion = FakeQuaternion(yaw_rad=0.2)
    gyro_lpf = FakeGyroLpf()
    state = ChassisState(
        wheel_states=[
            {"filtered_speed": 10.0},
            {"filtered_speed": 20.0},
            {"filtered_speed": 30.0},
        ],
        heading_est=90.0,
        odometry=odometry,
        kinematics=FakeKinematics(),
        gyro_lpf=gyro_lpf,
        q_est=quaternion,
        last_yaw_rad=0.1,
        imu=types.SimpleNamespace(get=lambda: [0, 0, 0, 1.0, 2.0, 3.0]),
        imu_offsets=[0.0, 0.0, 0.0, 0.5, 1.5, 2.5],
    )

    estimator.update_attitude(state, dt_s=0.02)

    assert len(odometry.calls) == 1
    _, _, theta_rad, dt_s = odometry.calls[0]
    assert math.isclose(theta_rad, math.radians(90.0), rel_tol=1e-9)
    assert dt_s == 0.02
    assert state.heading_est > 90.0
    assert state.last_gz_raw == 0.5
    assert state.yaw_rate == gyro_lpf.values[0] + 1.0


def test_attitude_estimator_unwraps_negative_pi_crossing() -> None:
    estimator = AttitudeEstimator()
    state = ChassisState(
        wheel_states=[
            {"filtered_speed": 0.0},
            {"filtered_speed": 0.0},
            {"filtered_speed": 0.0},
        ],
        heading_est=0.0,
        odometry=FakeOdometry(),
        kinematics=FakeKinematics(),
        gyro_lpf=FakeGyroLpf(),
        q_est=FakeQuaternion(yaw_rad=-math.pi + 0.1),
        last_yaw_rad=math.pi - 0.1,
        imu=types.SimpleNamespace(get=lambda: [0, 0, 0, 0.0, 0.0, 0.0]),
    )

    estimator.update_attitude(state, dt_s=0.01)

    assert state.heading_est > 0.0


def test_attitude_estimator_handles_empty_imu_sample() -> None:
    estimator = AttitudeEstimator()
    state = ChassisState(
        wheel_states=[
            {"filtered_speed": 0.0},
            {"filtered_speed": 0.0},
            {"filtered_speed": 0.0},
        ],
        heading_est=12.0,
        odometry=FakeOdometry(),
        kinematics=FakeKinematics(),
        gyro_lpf=FakeGyroLpf(),
        q_est=FakeQuaternion(yaw_rad=0.0),
        last_yaw_rad=0.0,
        imu=types.SimpleNamespace(get=lambda: None),
    )

    estimator.update_attitude(state, dt_s=0.01)

    assert state.imu_data is None
    assert state.last_gz_raw == 0.0
    assert state.yaw_rate == 1.0
