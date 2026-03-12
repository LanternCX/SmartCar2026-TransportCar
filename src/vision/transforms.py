"""视觉控制量与坐标转换辅助."""

import math


class VisionResolvedTarget:
    """由相对控制意图换算得到的绝对目标."""

    def __init__(self, x: float, y: float, angle_deg: float, rear_only_mode: bool):
        """保存本周期绝对位置与角度目标."""
        self.x = float(x)
        self.y = float(y)
        self.angle_deg = float(angle_deg)
        self.rear_only_mode = bool(rear_only_mode)


def normalize_angle(angle_deg: float) -> float:
    """将角度规范到 (-180, 180] 区间."""
    while angle_deg > 180.0:
        angle_deg -= 360.0
    while angle_deg <= -180.0:
        angle_deg += 360.0
    return angle_deg


def resolve_relative_intent(intent, odom_x: float, odom_y: float, heading_deg: float):
    """将相对控制意图转换为本周期绝对目标."""
    if not intent.active:
        return None

    theta_rad = math.radians(heading_deg)
    cos_t = math.cos(theta_rad)
    sin_t = math.sin(theta_rad)
    target_x = odom_x + intent.dx_body * cos_t - intent.dy_body * sin_t
    target_y = odom_y + intent.dx_body * sin_t + intent.dy_body * cos_t
    target_angle = normalize_angle(heading_deg + intent.d_angle_deg)
    return VisionResolvedTarget(target_x, target_y, target_angle, intent.rear_only_mode)
