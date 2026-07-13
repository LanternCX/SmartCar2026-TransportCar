"""轻量 Play 流程。"""

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


OP_END = const(0)
OP_POS_Y = const(1)
OP_ANGLE = const(2)
OP_LINE_Y = const(3)
OP_HOLD_Y = const(4)
OP_POS_Y_PARAM = const(5)
OP_ANGLE_PARAM = const(6)
OP_POS_XY_PARAM = const(7)
