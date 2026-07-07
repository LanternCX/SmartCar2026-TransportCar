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
_I8_MIN = const(-128)
_I8_MAX = const(127)
_SCALE = const(1000)
_ZERO_THRESHOLD = (0, 0, 0, 0, 0, 0)

LOCAL_VISION_CONTROL_PAUSE = const(1)
LOCAL_VISION_CONTROL_RESUME = const(2)
LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON = const(3)
LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF = const(4)


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


def _require_i8(value):
    value = int(value)
    if value < _I8_MIN or value > _I8_MAX:
        raise ValueError("i8 out of range")
    return value


def _pack_i8(value):
    value = _require_i8(value)
    if value < 0:
        value += 0x100
    return value


def _unpack_i8(body, offset):
    value = int(body[offset])
    if value >= 0x80:
        value -= 0x100
    return value


def _pack_threshold(threshold):
    if threshold is None:
        threshold = _ZERO_THRESHOLD
    if len(threshold) != 6:
        raise ValueError("threshold must have 6 values")
    return bytes(_pack_i8(value) for value in threshold)


def _unpack_threshold(body, offset):
    return tuple(_unpack_i8(body, offset + index) for index in range(6))


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
    return {
        "vx": _unpack_scaled(body, 0),
        "vy": _unpack_scaled(body, 2),
        "omega": _unpack_scaled(body, 4),
        "has_omega": bool(body[6]),
    }


def encode_vision_observation_body(context_id, x, y, value):
    return bytes([_require_u8(context_id)]) + _pack_scaled(x) + _pack_scaled(y) + _pack_scaled(value)


def decode_vision_observation_body(body):
    return {
        "context_id": int(body[0]),
        "x": _unpack_scaled(body, 1),
        "y": _unpack_scaled(body, 3),
        "value": _unpack_scaled(body, 5),
    }


def encode_local_vision_control_body(action):
    return bytes([_require_u8(action)])


def decode_local_vision_control_body(body):
    return {"action": int(body[0])}


def encode_master_vision_task_sync_body(context_id, state, target, arg):
    return bytes([_require_u8(context_id), _require_u8(state), _require_u8(target)]) + _pack_i16(arg)


def decode_master_vision_task_sync_body(body):
    return {
        "context_id": int(body[0]),
        "state": int(body[1]),
        "target": int(body[2]),
        "arg": _unpack_i16(body, 3),
    }


def encode_assistant_vision_task_sync_body(state, target, arg, threshold=None):
    return bytes([_require_u8(state), _require_u8(target)]) + _pack_i16(arg) + _pack_threshold(threshold)


def decode_assistant_vision_task_sync_body(body):
    return {
        "state": int(body[0]),
        "target": int(body[1]),
        "arg": _unpack_i16(body, 2),
        "threshold": _unpack_threshold(body, 4),
    }


def encode_master_vision_event_report_body(context_id, event, value, threshold=None):
    return bytes([_require_u8(context_id), _require_u8(event)]) + _pack_i16(value) + _pack_threshold(threshold)


def decode_master_vision_event_report_body(body):
    return {
        "context_id": int(body[0]),
        "event": int(body[1]),
        "value": _unpack_i16(body, 2),
        "threshold": _unpack_threshold(body, 4),
    }


def encode_assistant_vision_event_report_body(event, value):
    return bytes([_require_u8(event)]) + _pack_i16(value)


def decode_assistant_vision_event_report_body(body):
    return {
        "event": int(body[0]),
        "value": _unpack_i16(body, 1),
    }


def encode_assistant_state_sync_body(state, target, arg, threshold=None):
    return bytes([_require_u8(state), _require_u8(target)]) + _pack_i16(arg) + _pack_threshold(threshold)


def decode_assistant_state_sync_body(body):
    return {
        "state": int(body[0]),
        "target": int(body[1]),
        "arg": _unpack_i16(body, 2),
        "threshold": _unpack_threshold(body, 4),
    }


def encode_assistant_event_report_body(event, value):
    return bytes([_require_u8(event)]) + _pack_i16(value)


def decode_assistant_event_report_body(body):
    return {
        "event": int(body[0]),
        "value": _unpack_i16(body, 1),
    }
