"""主车运动学基线.

@file src/master/stability/kinematics.py
"""

import math


def body_axis_semantics():
    """返回车体系方向约定

    @brief 固定主车的方向和符号语义
    @return dict
    """

    return {
        "x_positive": "right",
        "y_positive": "forward",
        "omega_positive": "clockwise",
        "heading_positive": "clockwise",
    }


def rotate_body_delta_to_world(dx, dy, heading_deg):
    """将车体系位移增量旋转到世界系

    @brief 使用 x 右 y 前的车体系语义
    @param dx 车体系右向位移
    @param dy 车体系前向位移
    @param heading_deg 顺时针为正的朝向角
    @return tuple
    """

    theta = math.radians(float(heading_deg))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    world_x = dx * cos_t + dy * sin_t
    world_y = -dx * sin_t + dy * cos_t
    return world_x, world_y
