"""
@file src/protocol/frame.py
@brief 固定长度 bytes 帧编解码
"""

from config import comm as comm_params

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


MODE_UDP = const(0x01)
MODE_TCP = const(0x02)
MODE_ACK = const(0x03)

FRAME_BODY_SIZE = comm_params.TRANSPORT_FRAME_BODY_SIZE
FRAME_HEAD = comm_params.TRANSPORT_FRAME_HEAD
FRAME_SIZE = comm_params.TRANSPORT_FRAME_SIZE


def _require_u8(value):
    value = int(value)
    if value < 0 or value > 0xFF:
        raise ValueError("u8 out of range")
    return value


def _normalize_body(body):
    if isinstance(body, str):
        raise TypeError("body must be bytes-like")
    if isinstance(body, bytes):
        return body
    if isinstance(body, bytearray):
        return bytes(body)
    if isinstance(body, memoryview):
        return body.tobytes()
    raise TypeError("body must be bytes-like")


def _crc8(data):
    return _crc8_range(data, 0, len(data))


def _crc8_range(data, start, end):
    crc = 0
    for index in range(int(start), int(end)):
        value = data[index]
        crc ^= int(value)
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def encode_frame(mode, topic, seq, body):
    """编码固定帧."""

    mode = _require_u8(mode)
    topic = _require_u8(topic)
    seq = _require_u8(seq)
    body = _normalize_body(body)
    if len(body) > FRAME_BODY_SIZE:
        raise ValueError("body too large")
    payload = bytes([mode, topic, seq]) + body + (b"\x00" * (FRAME_BODY_SIZE - len(body)))
    return bytes([FRAME_HEAD]) + payload + bytes([_crc8(payload)])


def decode_frame_fields(frame_bytes, offset=0):
    """解码固定帧头字段，不拷贝 body。"""

    if not isinstance(frame_bytes, (bytes, bytearray, memoryview)):
        return None
    offset = int(offset)
    if offset < 0 or offset + FRAME_SIZE > len(frame_bytes):
        return None
    if frame_bytes[offset] != FRAME_HEAD:
        return None
    payload_start = offset + 1
    payload_end = offset + FRAME_SIZE - 1
    if _crc8_range(frame_bytes, payload_start, payload_end) != frame_bytes[payload_end]:
        return None
    return (
        int(frame_bytes[payload_start]),
        int(frame_bytes[payload_start + 1]),
        int(frame_bytes[payload_start + 2]),
    )


def decode_frame(frame_bytes):
    """解码固定帧."""

    if isinstance(frame_bytes, memoryview):
        frame_bytes = frame_bytes.tobytes()
    elif isinstance(frame_bytes, bytearray):
        frame_bytes = bytes(frame_bytes)
    if not isinstance(frame_bytes, bytes):
        return None
    fields = decode_frame_fields(frame_bytes, 0)
    if fields is None:
        return None
    mode, topic, seq = fields
    payload = frame_bytes[1:-1]
    return {
        "mode": mode,
        "topic": topic,
        "seq": seq,
        "body": payload[3:],
    }
