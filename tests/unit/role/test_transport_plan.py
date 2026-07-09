"""推动目标边解析测试."""

from role.transport_plan import (
    FIELD_EDGE_BOTTOM,
    FIELD_EDGE_LEFT,
    FIELD_EDGE_RIGHT,
    FIELD_EDGE_TOP,
    heading_with_offset,
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
    assert push_heading_for_edge(FIELD_EDGE_LEFT) == 90.0
    assert push_heading_for_edge(FIELD_EDGE_RIGHT) == -90.0


def test_heading_with_offset_wraps_to_control_range() -> None:
    """航向偏移结果保持在控制角度范围内."""

    assert heading_with_offset(180.0, 90.0) == -90.0
    assert heading_with_offset(-90.0, -180.0) == 90.0
