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
OBSTACLE_TYPE_BRICK = "brick"
OBSTACLE_TYPE_BUMP = "bump"
_ALL_OBJECTS = const(-1)


def limit_planar_velocity_step(prev_x, prev_y, target_x, target_y, max_delta):
    """限制二维速度向量的单拍变化量

    @brief 保持速度变化方向不变, 将相邻目标的距离限制在 max_delta 内
    @return 限幅后的 (x, y) 元组
    """
    delta_x = float(target_x) - float(prev_x)
    delta_y = float(target_y) - float(prev_y)
    delta_sq = delta_x * delta_x + delta_y * delta_y
    max_delta_sq = float(max_delta) * float(max_delta)
    if delta_sq > max_delta_sq:
        scale = float(max_delta) / math.sqrt(delta_sq)
        target_x = float(prev_x) + delta_x * scale
        target_y = float(prev_y) + delta_y * scale
    return float(target_x), float(target_y)


def target_edge_for_object(object_id, final_object=False):
    """按比赛模式、搬运进度和物体编号读取目标边."""

    if not bool(motion_params.IS_FINAL_ROUND) and final_object:
        return FIELD_EDGE_LEFT
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
    """按目标边、当前位置和障碍配置生成直线推动朝向"""
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
    minimum = float(motion_params.TRANSPORT_MIN_AVOIDANCE_ANGLE_DEG[target_edge])
    if not 0.0 <= minimum < 90.0:
        raise ValueError

    intervals = []
    for obstacle_type, edge, left, right in obstacle_slots:
        if obstacle_type not in (OBSTACLE_TYPE_BRICK, OBSTACLE_TYPE_BUMP):
            continue
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
        planned_heading = math.atan2(
            target_x - float(position_x),
            target_y - float(position_y),
        ) * 180.0 / math.pi
        push_heading = push_heading_for_edge(target_edge)
        offset = heading_with_offset(planned_heading, -push_heading)
        if abs(offset) < minimum:
            if offset == 0.0:
                toward_upper = endpoint == right
                positive_offset = toward_upper == (
                    target_edge in (FIELD_EDGE_TOP, FIELD_EDGE_LEFT)
                )
                offset = minimum if positive_offset else -minimum
            else:
                offset = minimum if offset > 0.0 else -minimum
            planned_heading = heading_with_offset(push_heading, offset)
        return planned_heading
    push_heading = push_heading_for_edge(target_edge)
    upper_half = coordinate >= axis_size / 2.0
    positive_offset = upper_half == (
        target_edge in (FIELD_EDGE_TOP, FIELD_EDGE_LEFT)
    )
    return heading_with_offset(
        push_heading,
        minimum if positive_offset else -minimum,
    )


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
    for obstacle_type, edge, left, _right in obstacle_slots:
        if obstacle_type != OBSTACLE_TYPE_BRICK:
            continue
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
    for obstacle_type, edge, left, right in obstacle_slots:
        if obstacle_type != OBSTACLE_TYPE_BRICK:
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


def _return_target_candidate(
    position_x,
    position_y,
    safe_end_y,
    rectangles,
    index,
):
    """按索引计算左侧安全边候选纵坐标."""

    if index == 0:
        return 0.0
    if index == 1:
        return safe_end_y
    corner_index = index - 2
    rectangle = rectangles[corner_index // 4]
    corner_index %= 4
    corner_x = rectangle[0] if corner_index < 2 else rectangle[1]
    if corner_x >= position_x - 1e-9:
        return None
    corner_y = rectangle[2] if corner_index % 2 == 0 else rectangle[3]
    scale = position_x / (position_x - corner_x)
    target_y = position_y + (corner_y - position_y) * scale
    if 0.0 <= target_y <= safe_end_y:
        return target_y
    return None


def _nearest_return_target_y(position_x, position_y, safe_end_y, rectangles):
    """选择左侧安全边上距离当前位置最近的可达纵坐标."""

    candidate_count = 2 + len(rectangles) * 4
    best_y = None
    best_distance = None
    current = None
    for index in range(candidate_count):
        candidate = _return_target_candidate(
            position_x,
            position_y,
            safe_end_y,
            rectangles,
            index,
        )
        if candidate is not None and (current is None or candidate < current):
            current = candidate

    while current is not None:
        if not _target_is_reachable(
            position_x,
            position_y,
            current,
            rectangles,
        ):
            distance = None
        else:
            distance = abs(current - position_y)
        if distance is not None and (
            best_distance is None or distance < best_distance
        ):
            best_y = current
            best_distance = distance

        next_candidate = None
        for index in range(candidate_count):
            candidate = _return_target_candidate(
                position_x,
                position_y,
                safe_end_y,
                rectangles,
                index,
            )
            if candidate is None or candidate <= current + 1e-9:
                continue
            if next_candidate is None or candidate < next_candidate:
                next_candidate = candidate
        if next_candidate is None:
            break

        middle = (current + next_candidate) * 0.5
        if not _target_is_reachable(
            position_x,
            position_y,
            middle,
            rectangles,
        ):
            current = next_candidate
            continue
        target_y = min(max(position_y, current), next_candidate)
        interval_distance = abs(target_y - position_y)
        if best_distance is None or interval_distance < best_distance:
            best_y = target_y
            best_distance = interval_distance
        current = next_candidate
    return best_y


def _return_point_axis(rectangles, safe_end_y, index, axis):
    """读取回库边界点的单轴坐标."""

    if index < 2:
        if axis == 0 or index == 0:
            return 0.0
        return safe_end_y
    corner_index = index - 2
    rectangle = rectangles[corner_index // 4]
    corner_index %= 4
    if axis == 0:
        return rectangle[0] if corner_index < 2 else rectangle[1]
    return rectangle[2] if corner_index % 2 == 0 else rectangle[3]


def _nearest_return_retreat(
    position_x,
    position_y,
    ray_x,
    ray_y,
    minimum_distance,
    safe_end_y,
    rectangles,
):
    """流式选择最短的可达后退距离和安全边目标."""

    point_count = 2 + len(rectangles) * 4
    current = minimum_distance
    while current is not None:
        candidate_x = position_x + current * ray_x
        candidate_y = position_y + current * ray_y
        target_y = _nearest_return_target_y(
            candidate_x,
            candidate_y,
            safe_end_y,
            rectangles,
        )
        if target_y is not None:
            return current, target_y

        next_candidate = None
        for first_index in range(point_count):
            first_x = _return_point_axis(rectangles, safe_end_y, first_index, 0)
            first_y = _return_point_axis(rectangles, safe_end_y, first_index, 1)
            for second_index in range(first_index + 1, point_count):
                second_x = _return_point_axis(rectangles, safe_end_y, second_index, 0)
                second_y = _return_point_axis(rectangles, safe_end_y, second_index, 1)
                line_x = second_x - first_x
                line_y = second_y - first_y
                denominator = ray_x * line_y - ray_y * line_x
                if abs(denominator) <= 1e-9:
                    continue
                distance = (
                    (first_x - position_x) * line_y
                    - (first_y - position_y) * line_x
                ) / denominator
                if distance < minimum_distance - 1e-9:
                    continue
                distance = max(minimum_distance, distance)
                if distance <= current + 1e-9:
                    continue
                if next_candidate is None or distance < next_candidate:
                    next_candidate = distance
        current = next_candidate
    return None, None


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
    distance_m, target_y = _nearest_return_retreat(
        x,
        y,
        ray_x,
        ray_y,
        minimum_m,
        safe_end_y,
        rectangles,
    )
    if distance_m is None or target_y is None:
        raise ValueError
    x += distance_m * ray_x
    y += distance_m * ray_y

    if abs(x) <= 1e-9 and abs(target_y - y) <= 1e-9:
        target_heading = push_heading_for_edge(FIELD_EDGE_LEFT)
    else:
        target_heading = math.atan2(-x, target_y - y) * 180.0 / math.pi
    return float(sign) * distance_m, target_heading
