"""主车姿态能力入口.

@file src/master/ctrl/attitude.py
"""

import math


def _clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _normalize_heading_error(error_deg):
    wrapped = math.fmod(float(error_deg) + 180.0, 360.0)
    if wrapped < 0.0:
        wrapped += 360.0
    return wrapped - 180.0


class HeadingEstimator:
    """保存姿态积分状态并对外提供航向估计结果."""

    def __init__(self):
        self.w = 1.0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

    def update(self, gx_deg_s, gy_deg_s, gz_deg_s, dt_s):
        gx = math.radians(float(gx_deg_s))
        gy = math.radians(float(gy_deg_s))
        gz = math.radians(float(gz_deg_s))
        q0 = self.w
        q1 = self.x
        q2 = self.y
        q3 = self.z
        dq0 = 0.5 * (-q1 * gx - q2 * gy - q3 * gz)
        dq1 = 0.5 * (q0 * gx + q2 * gz - q3 * gy)
        dq2 = 0.5 * (q0 * gy - q1 * gz + q3 * gx)
        dq3 = 0.5 * (q0 * gz + q1 * gy - q2 * gx)
        self.w += dq0 * dt_s
        self.x += dq1 * dt_s
        self.y += dq2 * dt_s
        self.z += dq3 * dt_s
        norm = math.sqrt(
            (self.w * self.w)
            + (self.x * self.x)
            + (self.y * self.y)
            + (self.z * self.z)
        )
        if norm == 0.0:
            self.w = 1.0
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            return
        inv_norm = 1.0 / norm
        self.w *= inv_norm
        self.x *= inv_norm
        self.y *= inv_norm
        self.z *= inv_norm

    def yaw_rad(self):
        return math.atan2(
            2.0 * ((self.w * self.z) + (self.x * self.y)),
            1.0 - (2.0 * ((self.y * self.y) + (self.z * self.z))),
        )

    def to_euler_yaw(self):
        return self.yaw_rad()


def quaternion_to_euler_deg(w, x, y, z):
    sinr_cosp = 2.0 * ((float(w) * float(x)) + (float(y) * float(z)))
    cosr_cosp = 1.0 - (2.0 * ((float(x) * float(x)) + (float(y) * float(y))))
    roll_rad = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * ((float(w) * float(y)) - (float(z) * float(x)))
    if sinp >= 1.0:
        pitch_rad = math.pi / 2.0
    elif sinp <= -1.0:
        pitch_rad = -math.pi / 2.0
    else:
        pitch_rad = math.asin(sinp)

    siny_cosp = 2.0 * ((float(w) * float(z)) + (float(x) * float(y)))
    cosy_cosp = 1.0 - (2.0 * ((float(y) * float(y)) + (float(z) * float(z))))
    yaw_rad = math.atan2(siny_cosp, cosy_cosp)
    return (
        math.degrees(roll_rad),
        math.degrees(pitch_rad),
        math.degrees(yaw_rad),
    )


def estimator_euler_deg(estimator):
    return quaternion_to_euler_deg(estimator.w, estimator.x, estimator.y, estimator.z)


def capture_heading_target(state):
    """在切换到保持模式时锁定当前航向目标."""

    state.target_heading_deg = float(state.heading_deg)
    state.yaw_integral = 0.0
    state.heading_target_ready = True


def ensure_heading_target(state):
    """只有尚未锁定目标时才初始化航向保持目标."""

    if not state.heading_target_ready:
        capture_heading_target(state)


def update_heading_from_gyro(state, heading_override=None):
    """根据当前 IMU 采样推进姿态积分并刷新航向估计."""

    gx_deg_s = float(state.imu_calibrated[3]) / float(state.gyro_scale)
    gy_deg_s = float(state.imu_calibrated[4]) / float(state.gyro_scale)
    gz_deg_s = float(state.imu_calibrated[5]) / float(state.gyro_scale)
    state.q_est.update(gx_deg_s, gy_deg_s, gz_deg_s, state.tick_s)
    curr_yaw_rad = state.q_est.yaw_rad()
    delta_yaw = curr_yaw_rad - state.last_yaw_rad
    if delta_yaw > math.pi:
        delta_yaw -= 2.0 * math.pi
    elif delta_yaw < -math.pi:
        delta_yaw += 2.0 * math.pi
    state.last_yaw_rad = curr_yaw_rad
    state.heading_deg += math.degrees(delta_yaw)
    state.yaw_rate_deg_s = state.gyro_lpf.update(gz_deg_s)
    if heading_override is not None:
        state.heading_deg = float(heading_override)
        state.last_yaw_rad = math.radians(state.heading_deg)
    ensure_heading_target(state)


def compute_heading_correction(state, heading_deg=None):
    """根据当前航向误差输出保持角速度."""

    if not getattr(state, "heading_hold_enabled", True):
        return 0.0
    if heading_deg is None:
        heading_deg = state.heading_deg
    error = _normalize_heading_error(
        float(state.target_heading_deg) - float(heading_deg)
    )
    state.yaw_integral += error
    state.yaw_integral = _clamp(state.yaw_integral, -state.yaw_i_max, state.yaw_i_max)
    omega = (error * state.yaw_kp) + (state.yaw_integral * state.yaw_ki)
    return _clamp(omega, -state.auto_omega_max, state.auto_omega_max)
