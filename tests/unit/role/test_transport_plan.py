"""推动目标边解析测试."""

import pytest

from role.transport_plan import (
    FIELD_EDGE_BOTTOM,
    FIELD_EDGE_LEFT,
    FIELD_EDGE_RIGHT,
    FIELD_EDGE_TOP,
    heading_with_offset,
    plan_transport_avoidance,
    push_heading_for_edge,
    target_edge_for_object,
)


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
    ("edge", "x", "y", "expected"),
    (
        (FIELD_EDGE_TOP, 1.30, 0.10, (-90.0, 5)),
        (FIELD_EDGE_BOTTOM, 1.90, 2.30, (-90.0, 5)),
        (FIELD_EDGE_LEFT, 0.10, 1.30, (-90.0, 5)),
        (FIELD_EDGE_RIGHT, 3.10, 1.90, (-90.0, 5)),
    ),
)
def test_transport_avoidance_uses_target_edge_axis_and_direction(
    edge: str, x: float, y: float, expected: "tuple[float, int]"
) -> None:
    """动态避障按目标边选择坐标轴和退出方向."""
    slots = ((edge, 1.45, 1.75), (None, -1.0, -1.0), (None, -1.0, -1.0))

    assert plan_transport_avoidance(edge, x, y, slots, 0.20, -90.0) == expected


def test_transport_avoidance_merges_touching_expanded_intervals() -> None:
    """扩展后相接的同边障碍合并为一个连续命中区间."""
    slots = (
        (FIELD_EDGE_TOP, 1.0, 1.2),
        (FIELD_EDGE_TOP, 1.6, 1.8),
        (FIELD_EDGE_RIGHT, 1.0, 1.5),
    )

    assert plan_transport_avoidance(
        FIELD_EDGE_TOP, 1.4, 0.0, slots, 0.20, -90.0
    ) == (-90.0, 60)


@pytest.mark.parametrize("x", (1.25, 1.95))
def test_transport_avoidance_treats_margin_boundaries_as_hits(x: float) -> None:
    """障碍 margin 的两个边界都按命中处理."""
    slots = (
        (FIELD_EDGE_TOP, 1.45, 1.75),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    result = plan_transport_avoidance(
        FIELD_EDGE_TOP, x, 0.0, slots, 0.20, -90.0
    )

    assert result is not None
    assert result[1] == 1


def test_transport_avoidance_returns_none_outside_matching_intervals() -> None:
    """坐标未命中或障碍属于其他边时不生成避障计划."""
    slots = (
        (FIELD_EDGE_BOTTOM, 1.45, 1.75),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    assert (
        plan_transport_avoidance(
            FIELD_EDGE_TOP, 1.60, 0.0, slots, 0.20, -90.0
        )
        is None
    )


@pytest.mark.parametrize(
    ("edge", "coordinate", "expected_offset"),
    (
        (FIELD_EDGE_TOP, 1.30, -90.0),
        (FIELD_EDGE_TOP, 1.90, 90.0),
        (FIELD_EDGE_BOTTOM, 1.30, 90.0),
        (FIELD_EDGE_BOTTOM, 1.90, -90.0),
        (FIELD_EDGE_LEFT, 1.30, -90.0),
        (FIELD_EDGE_LEFT, 1.90, 90.0),
        (FIELD_EDGE_RIGHT, 1.30, 90.0),
        (FIELD_EDGE_RIGHT, 1.90, -90.0),
    ),
)
def test_transport_avoidance_maps_exit_endpoint_to_orbit_offset(
    edge: str, coordinate: float, expected_offset: float
) -> None:
    """四条边的较小和较大退出端点映射到固定绕行方向."""
    slots = ((edge, 1.45, 1.75), (None, -1.0, -1.0), (None, -1.0, -1.0))
    x = coordinate if edge in (FIELD_EDGE_TOP, FIELD_EDGE_BOTTOM) else 0.0
    y = coordinate if edge in (FIELD_EDGE_LEFT, FIELD_EDGE_RIGHT) else 0.0

    result = plan_transport_avoidance(edge, x, y, slots, 0.20, -90.0)

    assert result is not None
    assert result[0] == expected_offset


def test_transport_avoidance_uses_default_offset_for_equal_distance() -> None:
    """命中区间中点使用配置的等距默认方向."""
    slots = (
        (FIELD_EDGE_TOP, 1.45, 1.75),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )

    assert plan_transport_avoidance(
        FIELD_EDGE_TOP, 1.60, 0.0, slots, 0.20, 90.0
    ) == (90.0, 35)
