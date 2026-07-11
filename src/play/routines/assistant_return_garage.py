"""辅车回库流程。"""

from play.routines import OP_ANGLE, OP_END, OP_HOLD_Y, OP_LINE_Y, OP_POS_Y

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value

# 辅车回库前先前进到主车让出的入口位置，单位 cm。
_LEAD_DISTANCE_CM = const(70)
_RETURN_POSITION_SPEED = const(5)
_RETURN_FORWARD_SPEED = const(3)
_FINAL_FORWARD_SPEED = const(8)
_FIRST_TURN_DEG = const(-90)
_FINAL_TURN_DEG = const(180)

SEQUENCE = (
    OP_POS_Y,
    _LEAD_DISTANCE_CM,
    _RETURN_POSITION_SPEED,
    OP_ANGLE,
    _FIRST_TURN_DEG,
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
