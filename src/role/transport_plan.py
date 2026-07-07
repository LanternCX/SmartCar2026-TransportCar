"""推动目标边解释

@file src/role/transport_plan.py
"""

from config import motion as motion_params


FIELD_EDGE_BOTTOM = "bottom"
FIELD_EDGE_TOP = "top"
FIELD_EDGE_LEFT = "left"
FIELD_EDGE_RIGHT = "right"
_ALL_OBJECTS = -1


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
        return 90.0
    if edge == FIELD_EDGE_RIGHT:
        return -90.0
    raise ValueError("unknown field edge")
