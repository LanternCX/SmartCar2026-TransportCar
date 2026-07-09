"""启动移动流程。"""

from play.routines import OP_ANGLE, OP_END, OP_POS_Y

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value

# 启动后第一段前进距离，单位 cm；解释器统一转换为 m。
_FIRST_FORWARD_DISTANCE_CM = const(70)
# 启动右转后第二段前进距离，单位 cm；用于进入取物搜索起点。
_SECOND_FORWARD_DISTANCE_CM = const(110)
_MOVE_SPEED = const(5)
_RIGHT_TURN_DEG = const(90)
_LEFT_TURN_DEG = const(-90)

SEQUENCE = (
    OP_POS_Y,
    _FIRST_FORWARD_DISTANCE_CM,
    _MOVE_SPEED,
    OP_ANGLE,
    _RIGHT_TURN_DEG,
    0,
    OP_POS_Y,
    _SECOND_FORWARD_DISTANCE_CM,
    _MOVE_SPEED,
    OP_ANGLE,
    _LEFT_TURN_DEG,
    0,
    OP_END,
    0,
    0,
)
