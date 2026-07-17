"""主车回库流程。"""

from play.routines import (
    OP_ANGLE,
    OP_ANGLE_PARAM,
    OP_END,
    OP_HOLD_Y,
    OP_LINE_Y,
    OP_POS_Y_PARAM,
)

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value

_RETURN_POSITION_SPEED = const(5)
_RETURN_FORWARD_SPEED = const(5)
_FINAL_FORWARD_SPEED = const(10)
_FINAL_TURN_DEG = const(180)

SEQUENCE = (
    OP_POS_Y_PARAM,
    0,
    _RETURN_POSITION_SPEED,
    OP_ANGLE_PARAM,
    1,
    0,
    OP_LINE_Y,
    _RETURN_FORWARD_SPEED,
    0,
    OP_ANGLE,
    _FINAL_TURN_DEG,
    0,
    OP_HOLD_Y,
    _FINAL_FORWARD_SPEED,
    0,
    OP_END,
    0,
    0,
)

FAST_SEQUENCE = (
    OP_ANGLE,
    _FINAL_TURN_DEG,
    0,
    OP_HOLD_Y,
    _FINAL_FORWARD_SPEED,
    0,
    OP_END,
    0,
    0,
)
