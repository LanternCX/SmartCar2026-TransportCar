"""! @brief 业务 body bytes 编解码测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.codec import (  # noqa: E402
    decode_assistant_event_report_body,
    decode_assistant_state_sync_body,
    decode_assistant_vision_event_report_body,
    decode_assistant_vision_task_sync_body,
    decode_master_vision_event_report_body,
    decode_master_vision_task_sync_body,
    decode_velocity_body,
    decode_vision_observation_body,
    encode_assistant_event_report_body,
    encode_assistant_state_sync_body,
    encode_assistant_vision_event_report_body,
    encode_assistant_vision_task_sync_body,
    encode_master_vision_event_report_body,
    encode_master_vision_task_sync_body,
    encode_velocity_body,
    encode_vision_observation_body,
)


def test_velocity_body_roundtrip_uses_little_endian_fixed_point() -> None:
    body = encode_velocity_body(1.25, -0.5, 0.75, True)

    assert body == bytes([0xE2, 0x04, 0x0C, 0xFE, 0xEE, 0x02, 0x01])
    assert decode_velocity_body(body) == {
        "vx": 1.25,
        "vy": -0.5,
        "omega": 0.75,
        "has_omega": True,
    }


def test_velocity_body_roundtrip_without_omega_flag() -> None:
    body = encode_velocity_body(0.08, -0.04, 0.0, False)

    assert decode_velocity_body(body) == {
        "vx": 0.08,
        "vy": -0.04,
        "omega": 0.0,
        "has_omega": False,
    }


def test_velocity_body_saturates_to_i16_range() -> None:
    body = encode_velocity_body(99.0, -99.0, 0.0, False)

    assert body[:6] == bytes([0xFF, 0x7F, 0x00, 0x80, 0x00, 0x00])


def test_vision_observation_body_roundtrip() -> None:
    body = encode_vision_observation_body(7, 1.0, -0.5, 3.0)

    assert body == bytes([7, 0xE8, 0x03, 0x0C, 0xFE, 0xB8, 0x0B])
    assert decode_vision_observation_body(body) == {
        "context_id": 7,
        "x": 1.0,
        "y": -0.5,
        "value": 3.0,
    }


def test_master_task_sync_body_roundtrip() -> None:
    body = encode_master_vision_task_sync_body(9, 1, 3, -2)

    assert body == bytes([9, 1, 3, 0xFE, 0xFF])
    assert decode_master_vision_task_sync_body(body) == {
        "context_id": 9,
        "state": 1,
        "target": 3,
        "arg": -2,
    }


def test_assistant_vision_task_sync_body_roundtrip() -> None:
    body = encode_assistant_vision_task_sync_body(2, 1, 17)

    assert body == bytes([2, 1, 17, 0])
    assert decode_assistant_vision_task_sync_body(body) == {
        "state": 2,
        "target": 1,
        "arg": 17,
    }


def test_master_vision_event_report_body_roundtrip() -> None:
    body = encode_master_vision_event_report_body(5, 6, 200)

    assert body == bytes([5, 6, 200, 0])
    assert decode_master_vision_event_report_body(body) == {
        "context_id": 5,
        "event": 6,
        "value": 200,
    }


def test_assistant_vision_event_report_body_roundtrip() -> None:
    body = encode_assistant_vision_event_report_body(7, -1)

    assert body == bytes([7, 0xFF, 0xFF])
    assert decode_assistant_vision_event_report_body(body) == {
        "event": 7,
        "value": -1,
    }


def test_assistant_state_sync_body_roundtrip() -> None:
    body = encode_assistant_state_sync_body(4, 1, 23)

    assert body == bytes([4, 1, 23, 0])
    assert decode_assistant_state_sync_body(body) == {
        "state": 4,
        "target": 1,
        "arg": 23,
    }


def test_assistant_event_report_body_roundtrip() -> None:
    body = encode_assistant_event_report_body(9, -3)

    assert body == bytes([9, 0xFD, 0xFF])
    assert decode_assistant_event_report_body(body) == {
        "event": 9,
        "value": -3,
    }


def test_codec_avoids_board_unstable_int_byte_helpers() -> None:
    source = (SRC / "protocol" / "codec.py").read_text(encoding="utf-8")

    assert ".to_bytes(" not in source
    assert "int.from_bytes(" not in source
