"""轻量 Play 指令解释器。"""

from play.routines import assistant_return_garage as _assistant_return_garage
from play.routines import master_return_garage as _master_return_garage
from play.routines import startup_move as _startup_move

PLAY_NONE = 0
PLAY_STARTUP = 1
PLAY_MASTER_RETURN = 2
PLAY_ASSISTANT_RETURN = 3

_OP_END = 0
_OP_POS_Y = 1
_OP_ANGLE = 2
_OP_LINE_Y = 3
_OP_HOLD_Y = 4


def start(runtime, kind):
    if int(runtime.play_kind) == int(kind):
        return
    runtime.play_kind = int(kind)
    runtime.play_step = 0
    runtime.play_entered = False


def clear(runtime):
    runtime.play_kind = PLAY_NONE
    runtime.play_step = 0
    runtime.play_entered = False


def tick(runtime):
    table = _table(runtime.play_kind)
    if table is None:
        return True
    while True:
        index = int(runtime.play_step) * 3
        op = int(table[index])
        value = int(table[index + 1])
        arg = int(table[index + 2])
        if op == _OP_END:
            clear(runtime)
            return True
        if _tick_op(runtime, op, value, arg):
            runtime.play_step = int(runtime.play_step) + 1
            runtime.play_entered = False
            continue
        return False


def _table(kind):
    kind = int(kind)
    if kind == PLAY_STARTUP:
        return _startup_move.SEQUENCE
    if kind == PLAY_MASTER_RETURN:
        return _master_return_garage.SEQUENCE
    if kind == PLAY_ASSISTANT_RETURN:
        return _assistant_return_garage.SEQUENCE
    return None


def _tick_op(runtime, op, value, arg):
    if op == _OP_POS_Y:
        if not runtime.play_entered:
            runtime.play_set_position_y(float(value) / 100.0, int(arg))
            runtime.play_entered = True
        return bool(runtime.play_motion_done())
    if op == _OP_ANGLE:
        if not runtime.play_entered:
            runtime.play_set_angle(value)
            runtime.play_entered = True
        return bool(runtime.play_motion_done())
    if op == _OP_LINE_Y:
        if not runtime.play_entered:
            runtime.play_clear_yellow_line_ready()
            runtime.play_enable_yellow_line_ready_gate()
            runtime.play_entered = True
        runtime.play_write_velocity_y(value)
        if not runtime.play_yellow_line_ready():
            return False
        runtime.play_disable_yellow_line_ready_gate()
        return True
    if op == _OP_HOLD_Y:
        runtime.play_write_velocity_y(value)
        return False
    return True
