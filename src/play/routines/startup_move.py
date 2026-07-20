"""启动移动流程。"""

from play.routines import OP_ANGLE, OP_END, OP_POS_XY_PARAM, OP_POS_Y

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value

# 启动右转后第二段前进距离，单位 cm；用于进入取物搜索起点。
_SECOND_FORWARD_DISTANCE_CM = const(90)
_FIRST_MOVE_SPEED = const(5)
_SECOND_MOVE_SPEED = const(5)
_STARTUP_HEADING_DEG = const(70)

SEQUENCE = (
    OP_POS_XY_PARAM,
    0,
    _FIRST_MOVE_SPEED,
    OP_ANGLE,
    _STARTUP_HEADING_DEG,
    0,
    OP_POS_Y,
    _SECOND_FORWARD_DISTANCE_CM,
    _SECOND_MOVE_SPEED,
    OP_END,
    0,
    0,
)

ASSISTANT_SEQUENCE = (
    OP_POS_XY_PARAM,
    0,
    _FIRST_MOVE_SPEED,
    OP_ANGLE,
    _STARTUP_HEADING_DEG,
    0,
    OP_END,
    0,
    0,
)
