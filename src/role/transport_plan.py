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
