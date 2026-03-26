"""辅车姿态解算基线

@file src/assistant/stability/attitude.py
"""

import math


def euler_to_quaternion(roll_deg, pitch_deg, yaw_deg):
    """欧拉角转四元数

    @brief 使用 legacy 的 Z-Y-X 欧拉角约定
    @param roll_deg 横滚角, 单位度
    @param pitch_deg 俯仰角, 单位度
    @param yaw_deg 偏航角, 单位度
    @return tuple[float, float, float, float]
    """

    roll_rad = math.radians(float(roll_deg)) * 0.5
    pitch_rad = math.radians(float(pitch_deg)) * 0.5
    yaw_rad = math.radians(float(yaw_deg)) * 0.5

    cr = math.cos(roll_rad)
    sr = math.sin(roll_rad)
    cp = math.cos(pitch_rad)
    sp = math.sin(pitch_rad)
    cy = math.cos(yaw_rad)
    sy = math.sin(yaw_rad)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return (w, x, y, z)


def quaternion_to_euler(quaternion):
    """四元数转欧拉角

    @brief 返回 roll/pitch/yaw, 单位度
    @param quaternion 四元数 `(w, x, y, z)`
    @return tuple[float, float, float]
    """

    w, x, y, z = quaternion
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll_rad = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    if sinp >= 1.0:
        pitch_rad = math.pi * 0.5
    elif sinp <= -1.0:
        pitch_rad = -math.pi * 0.5
    else:
        pitch_rad = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw_rad = math.atan2(siny_cosp, cosy_cosp)
    return (
        math.degrees(roll_rad),
        math.degrees(pitch_rad),
        math.degrees(yaw_rad),
    )
