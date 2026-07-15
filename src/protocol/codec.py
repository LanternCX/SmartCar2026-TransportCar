"""
@file src/protocol/codec.py
@brief 业务 body bytes 编解码
"""

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


_I16_MIN = const(-32768)
_I16_MAX = const(32767)
_SCALE = const(1000)

# 解码结果统一使用 tuple + const 索引，避免固定字段名进入板端 qstr 池。
VEL_X = const(0)
VEL_Y = const(1)
VEL_W = const(2)
VEL_HAS_W = const(3)

VO_CTX = const(0)
VO_X = const(1)
VO_Y = const(2)
VO_VALUE = const(3)

MT_CTX = const(0)
MT_STATE = const(1)
MT_TARGET = const(2)
MT_ARG = const(3)

AS_STATE = const(0)
AS_TARGET = const(1)
AS_ARG = const(2)

ME_CTX = const(0)
ME_EVENT = const(1)
ME_VALUE = const(2)

AE_EVENT = const(0)
AE_VALUE = const(1)

def _require_u8(value):
    value = int(value)
    if value < 0 or value > 0xFF:
        raise ValueError("u8 out of range")
    return value


def _saturate_i16(value):
    if value < _I16_MIN:
        return _I16_MIN
    if value > _I16_MAX:
        return _I16_MAX
    return value


def _pack_i16(value):
    value = _saturate_i16(int(value))
    if value < 0:
        value += 0x10000
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


def _unpack_i16(body, offset):
    value = int(body[offset]) | (int(body[offset + 1]) << 8)
    if value >= 0x8000:
        value -= 0x10000
    return value


def _pack_scaled(value):
    return _pack_i16(round(float(value) * _SCALE))


def _unpack_scaled(body, offset):
    return _unpack_i16(body, offset) / float(_SCALE)


def encode_velocity_body(vx, vy, omega, has_omega):
    return (
        _pack_scaled(vx)
        + _pack_scaled(vy)
        + _pack_scaled(omega)
        + bytes([1 if has_omega else 0])
    )


def decode_velocity_body(body):
    return (
        _unpack_scaled(body, 0),
        _unpack_scaled(body, 2),
        _unpack_scaled(body, 4),
        bool(body[6]),
    )


def decode_velocity_body_into(body, out):
    out[VEL_X] = _unpack_scaled(body, 0)
    out[VEL_Y] = _unpack_scaled(body, 2)
    out[VEL_W] = _unpack_scaled(body, 4)
    out[VEL_HAS_W] = bool(body[6])
    return out


def encode_vision_observation_body(context_id, x, y, value):
    return bytes([_require_u8(context_id)]) + _pack_scaled(x) + _pack_scaled(y) + _pack_scaled(value)


def decode_vision_observation_body(body):
    return (int(body[0]), _unpack_scaled(body, 1), _unpack_scaled(body, 3), _unpack_scaled(body, 5))


def encode_master_vision_task_sync_body(context_id, state, target, arg):
    return bytes([_require_u8(context_id), _require_u8(state), _require_u8(target)]) + _pack_i16(arg)


def decode_master_vision_task_sync_body(body):
    return (int(body[0]), int(body[1]), int(body[2]), _unpack_i16(body, 3))


def encode_assistant_vision_task_sync_body(state, target, arg):
    return bytes([_require_u8(state), _require_u8(target)]) + _pack_i16(arg)


def decode_assistant_vision_task_sync_body(body):
    return (int(body[0]), int(body[1]), _unpack_i16(body, 2))


def encode_master_vision_event_report_body(context_id, event, value):
    return bytes([_require_u8(context_id), _require_u8(event)]) + _pack_i16(value)


def decode_master_vision_event_report_body(body):
    return (int(body[0]), int(body[1]), _unpack_i16(body, 2))


def encode_assistant_vision_event_report_body(event, value):
    return bytes([_require_u8(event)]) + _pack_i16(value)


def decode_assistant_vision_event_report_body(body):
    return (int(body[0]), _unpack_i16(body, 1))


def encode_assistant_state_sync_body(state, target, arg):
    return bytes([_require_u8(state), _require_u8(target)]) + _pack_i16(arg)


def decode_assistant_state_sync_body(body):
    return (int(body[0]), int(body[1]), _unpack_i16(body, 2))


def encode_assistant_event_report_body(event, value):
    return bytes([_require_u8(event)]) + _pack_i16(value)


def decode_assistant_event_report_body(body):
    return (int(body[0]), _unpack_i16(body, 1))
