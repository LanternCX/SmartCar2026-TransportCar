"""串口短包协议解析与格式化工具.

@file src/vision/serial_protocol.py
"""

from config import comm as comm_params
import math


SEQ_MIN = getattr(comm_params, "SEQ_MIN")
SEQ_MAX = getattr(comm_params, "SEQ_MAX")
_SEQ_RING_SIZE = getattr(comm_params, "SEQ_RING_SIZE")
_SEQ_HALF_RING = getattr(comm_params, "SEQ_HALF_RING")


def _split_fields(line):
    text = line.strip()
    if not text:
        return None
    fields = [item.strip() for item in text.split(",")]
    if not fields or not fields[0]:
        return None
    for field in fields:
        if field == "":
            return None
    return fields


def _parse_float(text):
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _parse_int(text):
    try:
        value = int(text)
    except ValueError:
        return None
    if str(value) != text.strip():
        return None
    return value


def _parse_u8(text):
    value = _parse_int(text)
    if value is None or value < SEQ_MIN or value > SEQ_MAX:
        return None
    return value


def parse_short_packet(line):
    """解析一行短包协议.

    @param line 输入行文本
    @return 解析后的字段字典, 非法输入返回 None
    """

    fields = _split_fields(line)
    if fields is None:
        return None

    packet_type = fields[0].lower()
    if packet_type == "v":
        return _parse_velocity(fields)
    if packet_type == "s":
        return _parse_state_sync(fields)
    if packet_type == "a":
        return _parse_ack(fields)
    if packet_type == "r":
        return _parse_event(fields)
    if packet_type == "o":
        return _parse_observation(fields)
    return None


def _parse_velocity(fields):
    if len(fields) != 3 and len(fields) != 4:
        return None
    vx = _parse_float(fields[1])
    vy = _parse_float(fields[2])
    if vx is None or vy is None:
        return None
    has_omega = len(fields) == 4
    omega = 0.0
    if has_omega:
        omega = _parse_float(fields[3])
        if omega is None:
            return None
    return {
        "type": "v",
        "vx": vx,
        "vy": vy,
        "omega": omega,
        "has_omega": has_omega,
    }


def _parse_state_sync(fields):
    if len(fields) != 5:
        return None
    seq = _parse_u8(fields[1])
    state = _parse_u8(fields[2])
    target = _parse_u8(fields[3])
    arg = _parse_int(fields[4])
    if seq is None or state is None or target is None or arg is None:
        return None
    return {"type": "s", "seq": seq, "state": state, "target": target, "arg": arg}


def _parse_ack(fields):
    if len(fields) != 2:
        return None
    seq = _parse_u8(fields[1])
    if seq is None:
        return None
    return {"type": "a", "seq": seq}


def _parse_event(fields):
    if len(fields) != 4:
        return None
    seq = _parse_u8(fields[1])
    event = _parse_u8(fields[2])
    value = _parse_int(fields[3])
    if seq is None or event is None or value is None:
        return None
    return {"type": "r", "seq": seq, "event": event, "value": value}


def _parse_observation(fields):
    if len(fields) != 5:
        return None
    seq = _parse_u8(fields[1])
    x = _parse_float(fields[2])
    y = _parse_float(fields[3])
    value = _parse_float(fields[4])
    if seq is None or x is None or y is None or value is None:
        return None
    return {"type": "o", "seq": seq, "x": x, "y": y, "value": value}


def _require_u8(value):
    value = int(value)
    if value < SEQ_MIN or value > SEQ_MAX:
        raise ValueError("u8 out of range")
    return value


def format_velocity_packet(vx, vy, omega=None):
    """格式化速度短包."""

    if omega is None:
        return "v,%s,%s" % (float(vx), float(vy))
    return "v,%s,%s,%s" % (float(vx), float(vy), float(omega))


def format_state_sync_packet(seq, state, target, arg):
    """格式化状态同步短包."""

    return "s,%d,%d,%d,%d" % (
        _require_u8(seq),
        _require_u8(state),
        _require_u8(target),
        int(arg),
    )


def format_ack_packet(seq):
    """格式化确认短包."""

    return "a,%d" % _require_u8(seq)


def format_event_packet(seq, event, value):
    """格式化事件回报短包."""

    return "r,%d,%d,%d" % (_require_u8(seq), _require_u8(event), int(value))


def is_newer_seq(seq, last_seq):
    """按 0..255 环形序号判断 seq 是否新于 last_seq."""

    seq = _require_u8(seq)
    if last_seq is None:
        return True
    last_seq = _require_u8(last_seq)
    diff = (seq - last_seq) % _SEQ_RING_SIZE
    return diff != 0 and diff < _SEQ_HALF_RING
