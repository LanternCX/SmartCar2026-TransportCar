"""轻量 Play 指令解释器。"""

from play.routines import assistant_return_garage as _assistant_return_garage
from play.routines import master_return_garage as _master_return_garage
from play.routines import startup_move as _startup_move

PLAY_NONE = 0
PLAY_STARTUP = 1
PLAY_MASTER_RETURN = 2
PLAY_ASSISTANT_RETURN = 3
PLAY_ASSISTANT_STARTUP = 4
PLAY_MASTER_FAST_RETURN = 5
PLAY_ASSISTANT_FAST_RETURN = 6

_OP_END = 0
_OP_POS_Y = 1
_OP_ANGLE = 2
_OP_LINE_Y = 3
_OP_HOLD_Y = 4
_OP_POS_Y_PARAM = 5
_OP_ANGLE_PARAM = 6
_OP_POS_XY_PARAM = 7


def start(runtime, kind, params=None):
    if int(runtime.play_kind) == int(kind):
        return
    runtime.play_kind = int(kind)
    runtime.play_step = 0
    runtime.play_entered = False
    runtime.play_params = params


def clear(runtime):
    runtime.play_kind = PLAY_NONE
    runtime.play_step = 0
    runtime.play_entered = False
    runtime.play_params = None


def tick(runtime):
    table = _table(runtime.play_kind)
    if table is None:
        return True
    while True:
        index = int(runtime.play_step) * 3
        op = int(table[index])
        value = table[index + 1]
        arg = int(table[index + 2])
        if op in (_OP_POS_Y_PARAM, _OP_ANGLE_PARAM, _OP_POS_XY_PARAM):
            params = runtime.play_params
            if params is None:
                raise ValueError
            value = params[int(value)]
            if op == _OP_POS_Y_PARAM:
                op = _OP_POS_Y
            elif op == _OP_ANGLE_PARAM:
                op = _OP_ANGLE
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
    if kind == PLAY_ASSISTANT_STARTUP:
        return _startup_move.ASSISTANT_SEQUENCE
    if kind == PLAY_MASTER_RETURN:
        return _master_return_garage.SEQUENCE
    if kind == PLAY_ASSISTANT_RETURN:
        return _assistant_return_garage.SEQUENCE
    if kind == PLAY_MASTER_FAST_RETURN:
        return _master_return_garage.FAST_SEQUENCE
    if kind == PLAY_ASSISTANT_FAST_RETURN:
        return _assistant_return_garage.FAST_SEQUENCE
    return None


def _tick_op(runtime, op, value, arg):
    if op == _OP_POS_XY_PARAM:
        if not runtime.play_entered:
            runtime.play_set_position_xy(
                float(value[0]) / 100.0,
                float(value[1]) / 100.0,
                int(arg),
            )
            runtime.play_entered = True
        return bool(runtime.play_motion_done())
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
            runtime.play_clear_line_ready()
            runtime.play_entered = True
        runtime.play_write_velocity_y(value)
        if not runtime.play_line_ready():
            return False
        return True
    if op == _OP_HOLD_Y:
        runtime.play_write_velocity_y_limited(value)
        return False
    return True
