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
    state.last_attitude_time_us = int(now_us)
    if previous_us is None:
        return float(getattr(state, "tick_s", 0.0) or 0.0)
    dt_us = _ticks_diff_us(now_us, previous_us)
    dt_s = float(dt_us) / 1000000.0
    if dt_s <= 0.0:
        return float(getattr(state, "tick_s", 0.0) or 0.0)
    return dt_s


class HeadingEstimator:
    """保存姿态积分状态并对外提供航向估计结果."""

    def __init__(self):
        self.w = 1.0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

    def update(self, gx_deg_s, gy_deg_s, gz_deg_s, dt_s):
        """接收角速度角度制输入并转交四元数积分.

        @brief 给脚本诊断和运行时共用一个角度制入口, 避免外层重复做单位换算。
        """

        self.update_rad(
            math.radians(float(gx_deg_s)),
            math.radians(float(gy_deg_s)),
            math.radians(float(gz_deg_s)),
            dt_s,
        )

    def update_rad(self, gx_rad_s, gy_rad_s, gz_rad_s, dt_s):
        """按弧度制角速度推进四元数状态.

        @brief 这里只维护姿态积分和归一化, 不在这里夹带航向保持控制逻辑。
        """

        gx = float(gx_rad_s)
        gy = float(gy_rad_s)
        gz = float(gz_rad_s)
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
        """返回当前四元数对应的偏航角.

        @brief 运行时只关心偏航时, 通过这个入口读取最小姿态结果。
        """

        return math.atan2(
            2.0 * ((self.w * self.z) + (self.x * self.y)),
            1.0 - (2.0 * ((self.y * self.y) + (self.z * self.z))),
        )

    def to_euler_yaw(self):
        """提供与旧调用方一致的偏航读取入口.

        @brief 当前实现直接复用 `yaw_rad`, 让外层不必感知内部姿态表示。
        """

        return self.yaw_rad()


def quaternion_to_euler_deg(w, x, y, z):
    """把四元数展开成欧拉角角度制三元组.

    @brief 主要用于脚本观察和人工诊断, 不是控制链的主计算入口。
    """

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
    """读取估计器当前姿态并转换成角度制欧拉角.

    @brief 给调试脚本提供统一格式化前的数据入口。
    """

    return quaternion_to_euler_deg(estimator.w, estimator.x, estimator.y, estimator.z)


def capture_heading_target(state):
    """在切换到保持模式时锁定当前航向目标.

    @brief 同时清空积分项, 避免旧误差继续影响新的保持阶段。
    """

    state.target_heading_deg = float(state.heading_deg)
    state.yaw_integral = 0.0
    state.heading_target_ready = True


def ensure_heading_target(state):
    """只有尚未锁定目标时才初始化航向保持目标.

    @brief 把幂等保护收口在这里, 外层无需关心目标是否已经建立。
    """

    if not state.heading_target_ready:
        capture_heading_target(state)


def update_heading_from_gyro(state, heading_override=None, now_us=None):
    """根据当前 IMU 采样推进姿态积分并刷新航向估计.

    @brief 这个入口负责打通 IMU 校准值、四元数积分和连续航向角更新。
    """

    gx_deg_s, gy_deg_s, gz_deg_s = _normalize_gyro_deg_s(
        float(state.imu_calibrated[3]) / float(state.gyro_scale),
        float(state.imu_calibrated[4]) / float(state.gyro_scale),
        float(state.imu_calibrated[5]) / float(state.gyro_scale),
    )
    dt_s = _resolve_attitude_dt_s(state, now_us=now_us)
    state.tick_s = dt_s
    rad_scale = math.pi / 180.0
    state.q_est.update_rad(
        gx_deg_s * rad_scale,
        gy_deg_s * rad_scale,
        gz_deg_s * rad_scale,
        dt_s,
    )
    curr_yaw_rad = state.q_est.to_euler_yaw()
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
    """根据当前航向误差输出保持角速度.

    @brief 这里只计算航向保持角速度, 具体轮速分配留给后续控制链处理。
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
