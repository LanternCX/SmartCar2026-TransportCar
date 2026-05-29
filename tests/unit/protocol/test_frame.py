"""! @brief 固定帧编解码测试"""

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.frame import (  # noqa: E402
    FRAME_HEAD,
    FRAME_BODY_SIZE,
    FRAME_SIZE,
    MODE_ACK,
    MODE_TCP,
    MODE_UDP,
    decode_frame,
    encode_frame,
)


def test_encode_frame_uses_fixed_layout_and_zero_padding() -> None:
    frame = encode_frame(MODE_UDP, 0x02, 0x7F, b"\x01\x02\x03")

    assert frame[0] == FRAME_HEAD
    assert frame[1:12] == bytes([MODE_UDP, 0x02, 0x7F, 0x01, 0x02, 0x03, 0, 0, 0, 0, 0])
    assert len(frame) == FRAME_SIZE


def test_decode_frame_returns_header_and_fixed_body_bytes() -> None:
    frame = encode_frame(MODE_TCP, 0x20, 0x33, bytes([10, 11, 12]))

    assert decode_frame(frame) == {
        "mode": MODE_TCP,
        "topic": 0x20,
        "seq": 0x33,
        "body": bytes([10, 11, 12, 0, 0, 0, 0, 0]),
    }


def test_ack_frame_uses_empty_body_slot() -> None:
    frame = encode_frame(MODE_ACK, 0x21, 0x19, b"")

    parsed = decode_frame(frame)

    assert parsed is not None
    assert parsed["body"] == (b"\x00" * FRAME_BODY_SIZE)


def test_encode_frame_rejects_non_bytes_body() -> None:
    with pytest.raises(TypeError):
        encode_frame(MODE_UDP, 0x01, 0x00, "abc")


def test_encode_frame_rejects_body_larger_than_fixed_slot() -> None:
    with pytest.raises(ValueError):
        encode_frame(MODE_UDP, 0x01, 0x00, b"\x00" * (FRAME_BODY_SIZE + 1))


def test_decode_frame_rejects_wrong_length() -> None:
    assert decode_frame(b"\x01\x02") is None


def test_decode_frame_rejects_wrong_frame_head() -> None:
    frame = bytearray(encode_frame(MODE_UDP, 0x01, 0x00, b"\x01"))
    frame[0] = 0x00

    assert decode_frame(frame) is None


def test_decode_frame_rejects_crc_mismatch() -> None:
    frame = bytearray(encode_frame(MODE_UDP, 0x01, 0x00, b"\x01"))
    frame[-1] ^= 0x01

    assert decode_frame(frame) is None
