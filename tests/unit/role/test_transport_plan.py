"""搬运路径规划行为测试."""

import pytest
import role.transport_plan as transport_plan

from config import motion as motion_params
from role.transport_plan import (
    FIELD_EDGE_BOTTOM,
    FIELD_EDGE_LEFT,
    FIELD_EDGE_RIGHT,
    FIELD_EDGE_TOP,
    heading_with_offset,
    plan_transport_heading,
    push_heading_for_edge,
    target_edge_for_object,
)


MARGIN_M = float(motion_params.TRANSPORT_OBSTACLE_MARGIN_M)
FIELD_WIDTH_M = float(motion_params.FIELD_SIZE_M[0])
FIELD_HEIGHT_M = float(motion_params.FIELD_SIZE_M[1])


def _centered_obstacle(edge: str):
    axis_size = (
        FIELD_WIDTH_M
        if edge in (FIELD_EDGE_TOP, FIELD_EDGE_BOTTOM)
        else FIELD_HEIGHT_M
    )
    left = axis_size * 0.45
    right = axis_size * 0.55
    return ((edge, left, right), (None, -1.0, -1.0), (None, -1.0, -1.0))


def _lower_endpoint_diagonal_position(edge: str):
    slots = _centered_obstacle(edge)
    left, right = slots[0][1], slots[0][2]
    coordinate = (left + right) * 0.5
    distance = coordinate - (left - MARGIN_M)
    if edge == FIELD_EDGE_TOP:
        return slots, coordinate, FIELD_HEIGHT_M - distance
    if edge == FIELD_EDGE_BOTTOM:
        return slots, coordinate, distance
    if edge == FIELD_EDGE_LEFT:
        return slots, distance, coordinate
    return slots, FIELD_WIDTH_M - distance, coordinate


def test_transport_object_target_edge_uses_global_override() -> None:
    """-1 配置覆盖所有物体目标边."""

    edge = target_edge_for_object(1)

    assert edge in {
        FIELD_EDGE_BOTTOM,
        FIELD_EDGE_TOP,
        FIELD_EDGE_LEFT,
        FIELD_EDGE_RIGHT,
    }
    assert target_edge_for_object(255) == edge


def test_push_heading_is_derived_from_field_axes() -> None:
    """推动朝向由固定场地坐标系推导."""

    assert push_heading_for_edge(FIELD_EDGE_TOP) == 0.0
    assert push_heading_for_edge(FIELD_EDGE_BOTTOM) == 180.0
    assert push_heading_for_edge(FIELD_EDGE_LEFT) == -90.0
    assert push_heading_for_edge(FIELD_EDGE_RIGHT) == 90.0


def test_heading_with_offset_wraps_to_control_range() -> None:
    """航向偏移结果保持在控制角度范围内."""

    assert heading_with_offset(180.0, 90.0) == -90.0
    assert heading_with_offset(-90.0, -180.0) == 90.0


@pytest.mark.parametrize(
    ("edge", "expected_heading"),
    (
        (FIELD_EDGE_TOP, -45.0),
        (FIELD_EDGE_BOTTOM, -135.0),
        (FIELD_EDGE_LEFT, -135.0),
        (FIELD_EDGE_RIGHT, 135.0),
    ),
)
def test_transport_heading_targets_nearest_safe_endpoint(
    edge: str, expected_heading: float
) -> None:
    """命中障碍区间时直线指向最近的安全端点."""
    slots, x, y = _lower_endpoint_diagonal_position(edge)

    heading = plan_transport_heading(edge, x, y, slots, MARGIN_M)

    assert heading == pytest.approx(expected_heading)


def test_transport_heading_merges_touching_expanded_intervals() -> None:
    """扩展后相接的同边障碍合并为一个连续区间."""
    first_left = FIELD_WIDTH_M * 0.25
    first_right = FIELD_WIDTH_M * 0.35
    second_left = first_right + MARGIN_M * 2.0
    second_right = second_left + FIELD_WIDTH_M * 0.10
    slots = (
        (FIELD_EDGE_TOP, first_left, first_right),
        (FIELD_EDGE_TOP, second_left, second_right),
        (FIELD_EDGE_RIGHT, FIELD_HEIGHT_M * 0.25, FIELD_HEIGHT_M * 0.50),
    )
    lower_endpoint = first_left - MARGIN_M
    upper_endpoint = second_right + MARGIN_M
    coordinate = (lower_endpoint + upper_endpoint) * 0.5
    distance = coordinate - lower_endpoint

    heading = plan_transport_heading(
        FIELD_EDGE_TOP,
        coordinate,
        FIELD_HEIGHT_M - distance,
        slots,
        MARGIN_M,
    )

    assert heading == pytest.approx(-45.0)


@pytest.mark.parametrize("use_lower_endpoint", (True, False))
def test_transport_heading_treats_margin_boundaries_as_safe_endpoints(
    use_lower_endpoint: bool,
) -> None:
    """位于安全余量端点时可以直接垂直推动."""
    slots = _centered_obstacle(FIELD_EDGE_TOP)
    left, right = slots[0][1], slots[0][2]
    x = left - MARGIN_M if use_lower_endpoint else right + MARGIN_M

    assert plan_transport_heading(
        FIELD_EDGE_TOP, x, 0.0, slots, MARGIN_M
    ) == 0.0


def test_transport_heading_keeps_perpendicular_path_without_matching_obstacle() -> None:
    """未命中目标边障碍时保持既有垂直推动方向."""
    slots = _centered_obstacle(FIELD_EDGE_BOTTOM)

    assert plan_transport_heading(
        FIELD_EDGE_TOP, FIELD_WIDTH_M * 0.5, 0.0, slots, MARGIN_M
    ) == 0.0


def test_transport_heading_uses_lower_endpoint_when_distances_are_equal() -> None:
    """命中区间中点时确定性选择较小坐标端点."""
    slots, x, y = _lower_endpoint_diagonal_position(FIELD_EDGE_TOP)

    heading = plan_transport_heading(
        FIELD_EDGE_TOP, x, y, slots, MARGIN_M
    )

    assert heading == pytest.approx(-45.0)


def test_transport_heading_logs_world_position_on_each_check(monkeypatch) -> None:
    """每次路径规划都输出当前世界系坐标."""
    messages = []
    monkeypatch.setattr(
        transport_plan,
        "log",
        lambda stage, detail: messages.append((stage, detail)),
    )
    slots = ((None, -1.0, -1.0),) * 3
    top_x = FIELD_WIDTH_M * 0.375
    top_y = FIELD_HEIGHT_M * 0.125
    right_x = FIELD_WIDTH_M * 0.75
    right_y = FIELD_HEIGHT_M * 0.625

    plan_transport_heading(FIELD_EDGE_TOP, top_x, top_y, slots, MARGIN_M)
    plan_transport_heading(FIELD_EDGE_RIGHT, right_x, right_y, slots, MARGIN_M)

    assert messages == [
        ("path", "top x=%.3f y=%.3f" % (top_x, top_y)),
        ("path", "right x=%.3f y=%.3f" % (right_x, right_y)),
    ]
