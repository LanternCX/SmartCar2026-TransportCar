"""搬运目标边与直线路径规划

@file src/role/transport_plan.py
"""

import math

from config import motion as motion_params
from micropython import const  # pyright: ignore[reportMissingImports]
from utils.startup_log import log


FIELD_EDGE_BOTTOM = "bottom"
FIELD_EDGE_TOP = "top"
FIELD_EDGE_LEFT = "left"
FIELD_EDGE_RIGHT = "right"
_ALL_OBJECTS = const(-1)


def target_edge_for_object(object_id):
    """按物体编号读取目标边, -1 配置覆盖所有物体."""

    table = getattr(motion_params, "TRANSPORT_OBJECT_TARGET_EDGE")
    if _ALL_OBJECTS in table:
        return table[_ALL_OBJECTS]
    return table[int(object_id)]


def push_heading_for_edge(edge):
    """按场地坐标系推导推动朝向角."""

    edge = str(edge)
    if edge == FIELD_EDGE_TOP:
        return 0.0
    if edge == FIELD_EDGE_BOTTOM:
        return 180.0
    if edge == FIELD_EDGE_LEFT:
        return -90.0
    if edge == FIELD_EDGE_RIGHT:
        return 90.0
    raise ValueError("unknown field edge")


def plan_transport_heading(
    target_edge,
    position_x,
    position_y,
    obstacle_slots,
    margin_m,
):
    """按目标边、当前位置和障碍槽位生成直线推动朝向"""
    target_edge = str(target_edge)
    log("path", "%s x=%.3f y=%.3f" % (target_edge, position_x, position_y))
    margin_m = float(margin_m)
    if margin_m < 0.0:
        raise ValueError

    if target_edge in (FIELD_EDGE_TOP, FIELD_EDGE_BOTTOM):
        coordinate = float(position_x)
        axis_size = float(motion_params.FIELD_SIZE_M[0])
    elif target_edge in (FIELD_EDGE_LEFT, FIELD_EDGE_RIGHT):
        coordinate = float(position_y)
        axis_size = float(motion_params.FIELD_SIZE_M[1])
    else:
        raise ValueError

    intervals = []
    for edge, left, right in obstacle_slots:
        if edge != target_edge:
            continue
        intervals.append(
            (
                max(0.0, float(left) - margin_m),
                min(axis_size, float(right) + margin_m),
            )
        )
    intervals.sort()

    merged = []
    for left, right in intervals:
        if merged and left <= merged[-1][1] + 1e-9:
            if right > merged[-1][1]:
                merged[-1] = (merged[-1][0], right)
        else:
            merged.append((left, right))

    for left, right in merged:
        if not left <= coordinate <= right:
            continue
        lower_distance = coordinate - left
        upper_distance = right - coordinate
        endpoint = left if lower_distance <= upper_distance + 1e-9 else right
        if target_edge == FIELD_EDGE_TOP:
            target_x, target_y = endpoint, float(motion_params.FIELD_SIZE_M[1])
        elif target_edge == FIELD_EDGE_BOTTOM:
            target_x, target_y = endpoint, 0.0
        elif target_edge == FIELD_EDGE_LEFT:
            target_x, target_y = 0.0, endpoint
        else:
            target_x, target_y = float(motion_params.FIELD_SIZE_M[0]), endpoint
        return math.atan2(
            target_x - float(position_x),
            target_y - float(position_y),
        ) * 180.0 / math.pi
    return push_heading_for_edge(target_edge)


def heading_with_offset(heading_deg, offset_deg):
    """在场地角度坐标系中计算偏移后的航向角."""

    heading = float(heading_deg) + float(offset_deg)
    while heading > 180.0:
        heading -= 360.0
    while heading <= -180.0:
        heading += 360.0
    return heading


def _return_safe_end_y(obstacle_slots, margin_m):
    """计算原点到最近 left 障碍之间的安全边终点."""
    height = float(motion_params.FIELD_SIZE_M[1])
    safe_end_y = height
    has_left_obstacle = False
    for edge, left, _right in obstacle_slots:
        if edge != FIELD_EDGE_LEFT:
            continue
        has_left_obstacle = True
        low = max(0.0, float(left) - margin_m)
        if low < safe_end_y:
            safe_end_y = low
    return safe_end_y, has_left_obstacle


def plan_return_garage(
    position_x,
    position_y,
    heading_deg,
    longitudinal_sign,
    obstacle_slots,
    margin_m,
    obstacle_depth_m,
    extra_distance_m=0.0,
):
    """规划回库第一段车体系相对 Y 位移和第二段世界系绝对航向."""
    sign = int(longitudinal_sign)
    if sign not in (-1, 1):
        raise ValueError
    margin_m = float(margin_m)
    depth_m = float(obstacle_depth_m)
    extra_m = float(extra_distance_m)
    if margin_m < 0.0 or depth_m <= 0.0 or extra_m < 0.0:
        raise ValueError

    safe_end_y, has_left_obstacle = _return_safe_end_y(
        obstacle_slots,
        margin_m,
    )

    x = float(position_x)
    y = float(position_y)
    distance_m = 0.0
    heading_rad = math.radians(float(heading_deg))
    ray_x = float(sign) * math.sin(heading_rad)
    ray_y = float(sign) * math.cos(heading_rad)
    if has_left_obstacle:
        slope = safe_end_y / depth_m
        denominator = ray_y - slope * ray_x
        if abs(denominator) <= 1e-9:
            raise ValueError
        distance_m = (slope * x - y) / denominator
        if distance_m < 0.0:
            raise ValueError
    distance_m += extra_m
    x += distance_m * ray_x
    y += distance_m * ray_y

    if abs(x) <= 1e-9 and abs(y) <= 1e-9:
        target_heading = push_heading_for_edge(FIELD_EDGE_LEFT)
    else:
        target_heading = math.atan2(-x, -y) * 180.0 / math.pi
    return float(sign) * distance_m, target_heading
