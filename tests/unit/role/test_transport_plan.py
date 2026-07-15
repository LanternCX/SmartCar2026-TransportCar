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
    plan_return_garage,
    plan_startup_target_y,
    plan_transport_heading,
    push_heading_for_edge,
    target_edge_for_object,
)


MARGIN_M = float(motion_params.TRANSPORT_OBSTACLE_MARGIN_M)
FIELD_WIDTH_M = float(motion_params.FIELD_SIZE_M[0])
FIELD_HEIGHT_M = float(motion_params.FIELD_SIZE_M[1])


def test_startup_target_stops_at_nearest_left_obstacle_boundary() -> None:
    """出库第一段只受最近 left 障碍的原始边界限制."""
    slots = (
        (FIELD_EDGE_BOTTOM, 0.2, 0.4),
        (FIELD_EDGE_LEFT, 0.45, 0.8),
        (FIELD_EDGE_RIGHT, 0.3, 0.6),
    )

    assert plan_startup_target_y(slots, 0.7) == pytest.approx(0.45)


def test_startup_target_uses_configured_y_without_left_obstacle() -> None:
    """没有 left 障碍时使用配置的世界系绝对 Y 目标."""
    slots = (
        (FIELD_EDGE_BOTTOM, 0.2, 0.4),
        (FIELD_EDGE_RIGHT, 0.3, 0.6),
        (None, -1.0, -1.0),
    )

    assert plan_startup_target_y(slots, 0.7) == pytest.approx(0.7)


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


def test_transport_object_target_edge_uses_final_mapping(monkeypatch) -> None:
    """决赛按物体类别映射到三条目标边."""
    monkeypatch.setattr(
        motion_params,
        "TRANSPORT_OBJECT_TARGET_EDGE",
        {1: "left", 2: "left", 3: "right", 4: "right", 5: "top"},
    )

    assert tuple(target_edge_for_object(index) for index in range(1, 6)) == (
        "left",
        "left",
        "right",
        "right",
        "top",
    )


def test_transport_object_target_edge_uses_preliminary_override(monkeypatch) -> None:
    """初赛统一把所有物体搬运到底边."""
    monkeypatch.setattr(motion_params, "TRANSPORT_OBJECT_TARGET_EDGE", {-1: "bottom"})

    assert target_edge_for_object(1) == "bottom"
    assert target_edge_for_object(255) == "bottom"


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


def test_master_return_plan_uses_negative_relative_y_to_reach_boundary() -> None:
    """主车沿负 Y 方向移动到 O-C 终止边界."""
    slots = (
        (FIELD_EDGE_LEFT, 1.0, 1.4),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        0.5,
        1.5,
        -90.0,
        -1,
        slots,
        0.0,
        0.5,
    )

    assert relative_y_m == pytest.approx(-0.25)
    assert heading_deg == pytest.approx(-153.4349488)


def test_master_return_extra_retreat_updates_distance_and_approach_heading() -> None:
    """固定后退不足时移动到最近可达位置并计算斜入航向."""
    slots = (
        (FIELD_EDGE_LEFT, 1.0, 1.4),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        0.5,
        1.5,
        -90.0,
        -1,
        slots,
        0.0,
        0.5,
        0.2,
    )

    assert relative_y_m == pytest.approx(-0.25)
    assert heading_deg == pytest.approx(-153.4349488)


def test_assistant_return_plan_uses_positive_relative_y_to_reach_boundary() -> None:
    """辅车按相反航向沿正 Y 方向到达相同终止边界."""
    slots = (
        (FIELD_EDGE_LEFT, 1.0, 1.4),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        0.5,
        1.5,
        90.0,
        1,
        slots,
        0.0,
        0.5,
    )

    assert relative_y_m == pytest.approx(0.25)
    assert heading_deg == pytest.approx(-153.4349488)


@pytest.mark.parametrize(
    ("heading_deg", "longitudinal_sign", "minimum_retreat_m"),
    (
        (90.0, -1, motion_params.MASTER_RETURN_GARAGE_EXTRA_RETREAT_M),
        (-90.0, 1, motion_params.ASSISTANT_RETURN_GARAGE_EXTRA_RETREAT_M),
    ),
)
def test_return_plan_keeps_fixed_retreat_when_safe_edge_is_already_reachable(
    heading_deg: float,
    longitudinal_sign: int,
    minimum_retreat_m: float,
) -> None:
    """固定后退后已有无障碍斜入路径时不继续扩大第一段距离."""
    slots = (
        (FIELD_EDGE_LEFT, 1.05, 1.35),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, _heading_deg = plan_return_garage(
        FIELD_WIDTH_M,
        FIELD_HEIGHT_M * 0.5,
        heading_deg,
        longitudinal_sign,
        slots,
        MARGIN_M,
        motion_params.RETURN_GARAGE_OBSTACLE_DEPTH_M,
        minimum_retreat_m,
    )

    assert relative_y_m == pytest.approx(
        longitudinal_sign * float(minimum_retreat_m)
    )


def test_return_plan_extends_retreat_only_until_safe_edge_becomes_reachable() -> None:
    """固定后退仍被遮挡时只继续移动到最近的相切可达位置."""
    slots = (
        (FIELD_EDGE_LEFT, 1.0, 1.4),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, _heading_deg = plan_return_garage(
        0.0,
        1.2,
        -90.0,
        -1,
        slots,
        0.0,
        0.5,
        0.3,
    )

    assert relative_y_m == pytest.approx(-0.6)


def test_return_plan_retreats_past_right_obstacle_before_turning() -> None:
    """right 障碍遮挡斜入路径时后退到障碍内侧边界."""
    slots = (
        (FIELD_EDGE_RIGHT, 0.8, 1.6),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        FIELD_WIDTH_M,
        FIELD_HEIGHT_M * 0.5,
        90.0,
        -1,
        slots,
        0.0,
        0.5,
        0.3,
    )

    assert relative_y_m == pytest.approx(-0.5)
    assert heading_deg == pytest.approx(-90.0)


def test_return_plan_uses_current_position_when_safe_edge_is_directly_reachable() -> None:
    """当前位置已有无障碍路径时不增加第一阶段位移."""
    slots = (
        (FIELD_EDGE_LEFT, 1.0, 1.4),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        0.25,
        0.75,
        0.0,
        -1,
        slots,
        0.0,
        0.5,
    )

    assert relative_y_m == 0.0
    assert heading_deg == pytest.approx(-90.0)


def test_return_plan_avoids_bottom_obstacle_when_selecting_safe_edge_target() -> None:
    """bottom 障碍遮挡直线路径时选择相切的安全边目标."""
    slots = (
        (FIELD_EDGE_BOTTOM, 0.4, 0.6),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        1.0,
        0.2,
        -90.0,
        -1,
        slots,
        0.0,
        0.5,
    )

    assert relative_y_m == 0.0
    assert heading_deg == pytest.approx(-53.1301024)


def test_return_plan_uses_full_left_edge_without_left_obstacle() -> None:
    """没有 left 障碍时使用完整左边线选择最近目标."""
    slots = ((None, -1.0, -1.0),) * 3

    relative_y_m, heading_deg = plan_return_garage(
        1.0,
        FIELD_HEIGHT_M * 0.5,
        -90.0,
        -1,
        slots,
        MARGIN_M,
        0.5,
    )

    assert relative_y_m == 0.0
    assert heading_deg == pytest.approx(-90.0)


def test_return_plan_margin_only_expands_obstacle_along_left_edge() -> None:
    """margin 改变安全边端点但不增加障碍向场内深度."""
    margin_m = 0.2
    slots = (
        (FIELD_EDGE_LEFT, 1.0 + margin_m, 1.4 + margin_m),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        0.5,
        1.5,
        -90.0,
        -1,
        slots,
        margin_m,
        0.5,
    )

    assert relative_y_m == pytest.approx(-0.25)
    assert heading_deg == pytest.approx(-153.4349488)


def test_return_plan_keeps_stage_one_when_margin_closes_safe_edge() -> None:
    """margin 使安全边收缩为空时仍保留第一阶段."""
    slots = (
        (FIELD_EDGE_LEFT, 0.2, 0.5),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    relative_y_m, heading_deg = plan_return_garage(
        0.5,
        1.5,
        0.0,
        -1,
        slots,
        MARGIN_M,
        0.5,
    )

    assert relative_y_m == pytest.approx(-1.5)
    assert heading_deg == pytest.approx(-90.0)
