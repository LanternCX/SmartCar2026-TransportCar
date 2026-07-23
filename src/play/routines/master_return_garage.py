"""主车回库流程。"""

from play.routines import (
    OP_ANGLE,
    OP_ANGLE_PARAM,
    OP_END,
    OP_HOLD_Y,
    OP_LINE_Y,
    OP_POS_Y,
    OP_POS_Y_PARAM,
)

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value

# 决赛快速配置在此统一调整主车回库各段速度
# 回库位置控制段最大速度
_RETURN_POSITION_SPEED = const(8)
# 回库边线直行段速度
_RETURN_FORWARD_SPEED = const(8)
# 回库转向后的最后直行段速度
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
    OP_POS_Y,
    -8,
    _RETURN_POSITION_SPEED,
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
