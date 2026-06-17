"""! @brief 固定帧正式协议契约测试"""

import sys
from pathlib import Path


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
from protocol.topic import (  # noqa: E402
    ROLE_ASSISTANT,
    ROLE_MASTER,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_ASSISTANT_VISION_EVENT_REPORT,
    TOPIC_ASSISTANT_VISION_TASK_SYNC,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_EVENT_REPORT,
    TOPIC_MASTER_VISION_TASK_SYNC,
    TOPIC_VISION_OBSERVATION,
    UART6,
    UART8,
    can_role_read,
    can_role_write,
    get_topic_spec,
    validate_body_bytes,
)


def test_formal_transport_frame_is_fixed_length_bytes() -> None:
    frame = encode_frame(MODE_UDP, TOPIC_LOCAL_VISION_VELOCITY, 0x12, b"\x01\x02\x03\x04\x05\x06\x07")

    assert isinstance(frame, bytes)
    assert len(frame) == FRAME_SIZE
    assert frame[0] == FRAME_HEAD
    assert frame[1:4] == bytes([MODE_UDP, TOPIC_LOCAL_VISION_VELOCITY, 0x12])
    assert frame[4:12] == b"\x01\x02\x03\x04\x05\x06\x07\x00"
    assert decode_frame(frame) is not None


def test_ack_frame_has_zero_body_and_points_to_confirmed_topic_and_seq() -> None:
    parsed = decode_frame(encode_frame(MODE_ACK, TOPIC_ASSISTANT_STATE_SYNC, 0x34, b""))

    assert parsed == {
        "mode": MODE_ACK,
        "topic": TOPIC_ASSISTANT_STATE_SYNC,
        "seq": 0x34,
        "body": b"\x00" * FRAME_BODY_SIZE,
    }


def test_formal_topic_registry_matches_transport_contract() -> None:
    assert get_topic_spec(TOPIC_LOCAL_VISION_VELOCITY) == {
        "name": "LOCAL_VISION_VELOCITY",
        "mode": MODE_UDP,
        "port": UART6,
        "body_size": 7,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY) == {
        "name": "ASSISTANT_FEEDFORWARD_VELOCITY",
        "mode": MODE_UDP,
        "port": UART8,
        "body_size": 7,
    }
    assert get_topic_spec(TOPIC_VISION_OBSERVATION) == {
        "name": "VISION_OBSERVATION",
        "mode": MODE_UDP,
        "port": UART6,
        "body_size": 7,
    }
    assert get_topic_spec(TOPIC_MASTER_VISION_TASK_SYNC) == {
        "name": "MASTER_VISION_TASK_SYNC",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 5,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_VISION_TASK_SYNC) == {
        "name": "ASSISTANT_VISION_TASK_SYNC",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 10,
    }
    assert get_topic_spec(TOPIC_MASTER_VISION_EVENT_REPORT) == {
        "name": "MASTER_VISION_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 10,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_VISION_EVENT_REPORT) == {
        "name": "ASSISTANT_VISION_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 3,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_STATE_SYNC) == {
        "name": "ASSISTANT_STATE_SYNC",
        "mode": MODE_TCP,
        "port": UART8,
        "body_size": 10,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_EVENT_REPORT) == {
        "name": "ASSISTANT_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART8,
        "body_size": 3,
    }


def test_formal_transport_body_rejects_strings_and_wrong_lengths() -> None:
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, "abc") is False
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, b"\x00" * 6) is False
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, b"\x00" * 7) is True


def test_formal_transport_role_directions_are_fixed() -> None:
    assert can_role_read(TOPIC_LOCAL_VISION_VELOCITY, ROLE_MASTER) is True
    assert can_role_write(TOPIC_LOCAL_VISION_VELOCITY, ROLE_MASTER) is False
    assert can_role_write(TOPIC_MASTER_VISION_TASK_SYNC, ROLE_MASTER) is True
    assert can_role_read(TOPIC_MASTER_VISION_TASK_SYNC, ROLE_MASTER) is False
    assert can_role_write(TOPIC_ASSISTANT_VISION_TASK_SYNC, ROLE_ASSISTANT) is True
    assert can_role_read(TOPIC_ASSISTANT_VISION_TASK_SYNC, ROLE_ASSISTANT) is False
    assert can_role_write(TOPIC_ASSISTANT_EVENT_REPORT, ROLE_ASSISTANT) is True
    assert can_role_read(TOPIC_ASSISTANT_EVENT_REPORT, ROLE_MASTER) is True
