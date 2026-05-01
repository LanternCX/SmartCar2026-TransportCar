"""! @brief 串口短包协议解析测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.packet import (  # noqa: E402
    format_ack_packet,
    format_event_packet,
    format_observation_packet,
    format_state_sync_packet,
    format_velocity_packet,
    is_later_ring_value,
    parse_short_packet,
)


def test_parse_velocity_packet_with_omega() -> None:
    packet = parse_short_packet("v,1.25,-0.5,0.75")

    assert packet == {
        "type": "v",
        "vx": 1.25,
        "vy": -0.5,
        "omega": 0.75,
        "has_omega": True,
    }


def test_parse_velocity_packet_without_omega() -> None:
    packet = parse_short_packet("v,1.25,-0.5")

    assert packet == {
        "type": "v",
        "vx": 1.25,
        "vy": -0.5,
        "omega": 0.0,
        "has_omega": False,
    }


def test_parse_state_sync_ack_event_and_observation_packets() -> None:
    assert parse_short_packet("s,12,7,3,1,0") == {
        "type": "s",
        "reliable_seq": 12,
        "context_id": 7,
        "state": 3,
        "target": 1,
        "arg": 0,
    }
    assert parse_short_packet("a,12") == {"type": "a", "reliable_seq": 12}
    assert parse_short_packet("r,13,7,2,-1") == {
        "type": "r",
        "reliable_seq": 13,
        "context_id": 7,
        "event": 2,
        "value": -1,
    }
    assert parse_short_packet("o,7,1.0,-0.5,3.0") == {
        "type": "o",
        "context_id": 7,
        "x": 1.0,
        "y": -0.5,
        "value": 3.0,
    }


def test_parse_short_packet_rejects_invalid_values() -> None:
    invalid_lines = [
        "",
        "v,1",
        "v,1,2,3,4",
        "v,1,nan",
        "v,1,inf",
        "s,256,7,3,1,0",
        "s,12,256,3,1,0",
        "s,12,7,256,1,0",
        "s,12,7,3,-1,0",
        "a,-1",
        "r,12,7,256,0",
        "r,12,256,2,0",
        "o,7,1,2,nan",
        "x,1,2",
    ]

    for line in invalid_lines:
        assert parse_short_packet(line) is None


def test_format_short_packets() -> None:
    assert format_velocity_packet(1.0, -2.5, 0.5) == "v,1.0,-2.5,0.5"
    assert format_velocity_packet(1.0, -2.5) == "v,1.0,-2.5"
    assert format_state_sync_packet(12, 7, 3, 1, 0) == "s,12,7,3,1,0"
    assert format_ack_packet(12) == "a,12"
    assert format_observation_packet(7, 1.0, -0.5, 3.0) == "o,7,1.0,-0.5,3.0"
    assert format_event_packet(13, 7, 2, -1) == "r,13,7,2,-1"


def test_is_later_ring_value_uses_ring_order() -> None:
    assert is_later_ring_value(1, None) is True
    assert is_later_ring_value(13, 12) is True
    assert is_later_ring_value(0, 255) is True
    assert is_later_ring_value(12, 12) is False
    assert is_later_ring_value(11, 12) is False
    assert is_later_ring_value(255, 0) is False
