"""辅车姿态能力入口.

@file src/assistant/ctrl/attitude.py
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


def _read_now_us():
    import time

    ticks_us = getattr(time, "ticks_us", None)
    if ticks_us is not None:
        return int(ticks_us())
    return int(time.time() * 1000000)


def _ticks_diff_us(current_us, previous_us):
    import time

    ticks_diff = getattr(time, "ticks_diff", None)
    if ticks_diff is not None:
        return int(ticks_diff(int(current_us), int(previous_us)))
    return int(current_us) - int(previous_us)


def _normalize_gyro_deg_s(gx_deg_s, gy_deg_s, gz_deg_s):
    return (
        round(float(gx_deg_s), 1),
        round(float(gy_deg_s), 1),
        round(float(gz_deg_s), 1),
    )


def _resolve_attitude_dt_s(state, now_us=None):
    if now_us is None:
        now_us = _read_now_us()
    previous_us = getattr(state, "last_attitude_time_us", None)
    if previous_us is None:
        state.last_attitude_time_us = int(now_us)
        return 0.0
    dt_us = _ticks_diff_us(now_us, previous_us)
    dt_s = float(dt_us) / 1000000.0
    if dt_s <= 0.0:
        return 0.0
    state.last_attitude_time_us = int(now_us)
    return dt_s


class HeadingEstimator:
    """保存姿态积分状态并对外提供航向估计结果."""

    def __init__(self):
        self.w = 1.0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

    def update(self, gx_deg_s, gy_deg_s, gz_deg_s, dt_s):
        """按单拍角速度推进四元数积分.

        @brief 用 IMU 角速度刷新姿态估计, 给航向保持和诊断脚本复用。
        """

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
        """从当前四元数中提取偏航角.

        @brief 给运行时航向保持提供连续 yaw 估计。
        """

        return math.atan2(
            2.0 * ((self.w * self.z) + (self.x * self.y)),
            1.0 - (2.0 * ((self.y * self.y) + (self.z * self.z))),
        )


def capture_heading_target(state):
    """锁定当前航向为保持目标.

    @brief 在辅车进入稳定跟随或停驻时清空积分并固定目标角。
    """

    state.target_heading_deg = float(state.heading_deg)
    state.yaw_integral = 0.0
    state.heading_target_ready = True


def ensure_heading_target(state):
    """在需要时补齐航向保持目标.

    @brief 避免多个控制入口重复判断是否已经锁定目标角。
    """

    if not state.heading_target_ready:
        capture_heading_target(state)


def update_heading_from_gyro(state, heading_override=None, now_us=None):
    """根据 IMU 采样推进当前航向估计.

    @brief 统一完成时间步长解析、四元数积分和可选的外部航向覆盖。
    """

    gx_deg_s, gy_deg_s, gz_deg_s = _normalize_gyro_deg_s(
        float(state.imu_calibrated[3]) / float(state.gyro_scale),
        float(state.imu_calibrated[4]) / float(state.gyro_scale),
        float(state.imu_calibrated[5]) / float(state.gyro_scale),
    )
    state.tick_s = _resolve_attitude_dt_s(state, now_us=now_us)
    if state.tick_s <= 0.0:
        if heading_override is not None:
            state.heading_deg = float(heading_override)
            state.last_yaw_rad = math.radians(state.heading_deg)
        ensure_heading_target(state)
        return
    state.q_est.update(gx_deg_s, gy_deg_s, gz_deg_s, state.tick_s)
    curr_yaw_rad = state.q_est.yaw_rad()
    delta_yaw = curr_yaw_rad - state.last_yaw_rad
    if delta_yaw > math.pi:
        delta_yaw -= 2.0 * math.pi
    elif delta_yaw < -math.pi:
        delta_yaw += 2.0 * math.pi
    state.last_yaw_rad = curr_yaw_rad
    state.heading_deg += math.degrees(delta_yaw)
    state.yaw_rate_deg_s = gz_deg_s
    if heading_override is not None:
        state.heading_deg = float(heading_override)
        state.last_yaw_rad = math.radians(state.heading_deg)
    ensure_heading_target(state)


def compute_heading_correction(state, heading_deg=None):
    """根据航向误差生成保持角速度.

    @brief 用辅车运行时保存的 PID 参数计算偏航修正输出。
    """

    if not getattr(state, "heading_hold_enabled", True):
        return 0.0
    if heading_deg is None:
        heading_deg = state.heading_deg
    error = _normalize_heading_error(
        float(state.target_heading_deg) - float(heading_deg)
    )
    dt_s = float(getattr(state, "tick_s", 0.0) or 0.0)
    state.yaw_integral += error * dt_s
    state.yaw_integral = _clamp(
        state.yaw_integral,
        -float(state.yaw_i_max),
        float(state.yaw_i_max),
    )
    omega = (error * state.yaw_kp) + (state.yaw_integral * state.yaw_ki)
    omega -= float(getattr(state, "yaw_rate_deg_s", 0.0)) * float(
        getattr(state, "yaw_kd", 0.0)
    )
    return _clamp(omega, -state.auto_omega_max, state.auto_omega_max)
