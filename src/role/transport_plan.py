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


def _left_safe_end_y(obstacle_slots, margin_m):
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


def _return_rectangles(obstacle_slots, margin_m, depth_m):
    """生成回库直线路径碰撞判断使用的障碍矩形."""
    width = float(motion_params.FIELD_SIZE_M[0])
    height = float(motion_params.FIELD_SIZE_M[1])
    rectangles = []
    for edge, left, right in obstacle_slots:
        if edge is None:
            continue
        left = float(left)
        right = float(right)
        if edge == FIELD_EDGE_LEFT or edge == FIELD_EDGE_RIGHT:
            low = max(0.0, left - margin_m)
            high = min(height, right + margin_m)
            if edge == FIELD_EDGE_LEFT:
                rectangles.append((0.0, depth_m, low, high))
            else:
                rectangles.append((width - depth_m, width, low, high))
        elif edge == FIELD_EDGE_BOTTOM or edge == FIELD_EDGE_TOP:
            low = max(0.0, left - margin_m)
            high = min(width, right + margin_m)
            if edge == FIELD_EDGE_BOTTOM:
                rectangles.append((low, high, 0.0, depth_m))
            else:
                rectangles.append((low, high, height - depth_m, height))
        else:
            raise ValueError
    return rectangles


def _open_axis_interval(start, end, lower, upper):
    """计算线段落入一维开区间时对应的参数区间."""
    delta = end - start
    if abs(delta) <= 1e-9:
        if lower < start < upper:
            return 0.0, 1.0
        return None
    first = (lower - start) / delta
    second = (upper - start) / delta
    if first > second:
        first, second = second, first
    return first, second


def _segment_crosses_rectangle(position_x, position_y, target_y, rectangle):
    """判断当前位置到左侧安全边目标的线段是否穿过矩形内部."""
    x_low, x_high, y_low, y_high = rectangle
    x_interval = _open_axis_interval(position_x, 0.0, x_low, x_high)
    if x_interval is None:
        return False
    y_interval = _open_axis_interval(position_y, target_y, y_low, y_high)
    if y_interval is None:
        return False
    lower = max(0.0, x_interval[0], y_interval[0])
    upper = min(1.0, x_interval[1], y_interval[1])
    return lower < upper - 1e-9


def _target_is_reachable(position_x, position_y, target_y, rectangles):
    for rectangle in rectangles:
        if _segment_crosses_rectangle(
            position_x,
            position_y,
            target_y,
            rectangle,
        ):
            return False
    return True


def _nearest_return_target_y(position_x, position_y, safe_end_y, rectangles):
    """选择左侧安全边上距离当前位置最近的可达纵坐标."""
    candidates = [0.0, safe_end_y]
    for x_low, x_high, y_low, y_high in rectangles:
        for corner_x in (x_low, x_high):
            if corner_x >= position_x - 1e-9:
                continue
            scale = position_x / (position_x - corner_x)
            for corner_y in (y_low, y_high):
                target_y = position_y + (corner_y - position_y) * scale
                if 0.0 <= target_y <= safe_end_y:
                    candidates.append(target_y)
    candidates.sort()

    unique = []
    for target_y in candidates:
        if not unique or abs(target_y - unique[-1]) > 1e-9:
            unique.append(target_y)

    best_y = None
    best_distance = None
    for target_y in unique:
        if not _target_is_reachable(
            position_x,
            position_y,
            target_y,
            rectangles,
        ):
            continue
        distance = abs(target_y - position_y)
        if best_distance is None or distance < best_distance:
            best_y = target_y
            best_distance = distance

    for index in range(len(unique) - 1):
        lower = unique[index]
        upper = unique[index + 1]
        middle = (lower + upper) * 0.5
        if not _target_is_reachable(
            position_x,
            position_y,
            middle,
            rectangles,
        ):
            continue
        target_y = min(max(position_y, lower), upper)
        distance = abs(target_y - position_y)
        if best_distance is None or distance < best_distance:
            best_y = target_y
            best_distance = distance
    return best_y


def _return_retreat_candidates(
    position_x,
    position_y,
    ray_x,
    ray_y,
    minimum_distance,
    safe_end_y,
    rectangles,
):
    """生成后退射线经过可达性变化边界时的距离候选."""
    points = [(0.0, 0.0), (0.0, safe_end_y)]
    for x_low, x_high, y_low, y_high in rectangles:
        points.extend(
            (
                (x_low, y_low),
                (x_low, y_high),
                (x_high, y_low),
                (x_high, y_high),
            )
        )

    candidates = [minimum_distance]
    for first_index in range(len(points)):
        first_x, first_y = points[first_index]
        for second_index in range(first_index + 1, len(points)):
            second_x, second_y = points[second_index]
            line_x = second_x - first_x
            line_y = second_y - first_y
            denominator = ray_x * line_y - ray_y * line_x
            if abs(denominator) <= 1e-9:
                continue
            distance = (
                (first_x - position_x) * line_y
                - (first_y - position_y) * line_x
            ) / denominator
            if distance >= minimum_distance - 1e-9:
                candidates.append(max(minimum_distance, distance))
    candidates.sort()

    unique = []
    for distance in candidates:
        if not unique or abs(distance - unique[-1]) > 1e-9:
            unique.append(distance)
    return unique


def plan_startup_target_y(obstacle_slots, target_y):
    """规划出库第一段的世界系绝对 Y 目标."""
    safe_end_y, _ = _left_safe_end_y(obstacle_slots, 0.0)
    return min(float(target_y), safe_end_y)


def plan_return_garage(
    position_x,
    position_y,
    heading_deg,
    longitudinal_sign,
    obstacle_slots,
    margin_m,
    obstacle_depth_m,
    minimum_retreat_m=0.0,
):
    """规划回库第一段车体系相对 Y 位移和第二段世界系绝对航向."""
    sign = int(longitudinal_sign)
    if sign not in (-1, 1):
        raise ValueError
    margin_m = float(margin_m)
    depth_m = float(obstacle_depth_m)
    minimum_m = float(minimum_retreat_m)
    if margin_m < 0.0 or depth_m <= 0.0 or minimum_m < 0.0:
        raise ValueError

    safe_end_y, _has_left_obstacle = _left_safe_end_y(
        obstacle_slots,
        margin_m,
    )
    rectangles = _return_rectangles(obstacle_slots, margin_m, depth_m)

    x = float(position_x)
    y = float(position_y)
    heading_rad = math.radians(float(heading_deg))
    ray_x = float(sign) * math.sin(heading_rad)
    ray_y = float(sign) * math.cos(heading_rad)
    distance_m = None
    target_y = None
    for candidate in _return_retreat_candidates(
        x,
        y,
        ray_x,
        ray_y,
        minimum_m,
        safe_end_y,
        rectangles,
    ):
        candidate_x = x + candidate * ray_x
        candidate_y = y + candidate * ray_y
        candidate_target_y = _nearest_return_target_y(
            candidate_x,
            candidate_y,
            safe_end_y,
            rectangles,
        )
        if candidate_target_y is None:
            continue
        distance_m = candidate
        target_y = candidate_target_y
        x = candidate_x
        y = candidate_y
        break
    if distance_m is None or target_y is None:
        raise ValueError

    if abs(x) <= 1e-9 and abs(target_y - y) <= 1e-9:
        target_heading = push_heading_for_edge(FIELD_EDGE_LEFT)
    else:
        target_heading = math.atan2(-x, target_y - y) * 180.0 / math.pi
    return float(sign) * distance_m, target_heading
