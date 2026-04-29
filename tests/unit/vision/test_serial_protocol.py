"""串口短包协议解析测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.serial_protocol import (  # noqa: E402
    format_ack_packet,
    format_event_packet,
    format_state_sync_packet,
    format_velocity_packet,
    is_newer_seq,
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
    assert parse_short_packet("s,12,3,1,0") == {
        "type": "s",
        "seq": 12,
        "state": 3,
        "target": 1,
        "arg": 0,
    }
    assert parse_short_packet("a,12") == {"type": "a", "seq": 12}
    assert parse_short_packet("r,12,2,-1") == {
        "type": "r",
        "seq": 12,
        "event": 2,
        "value": -1,
    }
    assert parse_short_packet("o,12,1.0,-0.5,3.0") == {
        "type": "o",
        "seq": 12,
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
        "s,256,3,1,0",
        "s,12,256,1,0",
        "s,12,3,-1,0",
        "a,-1",
        "r,12,256,0",
        "o,12,1,2,nan",
        "x,1,2",
    ]

    for line in invalid_lines:
        assert parse_short_packet(line) is None


def test_format_short_packets() -> None:
    assert format_velocity_packet(1.0, -2.5, 0.5) == "v,1.0,-2.5,0.5"
    assert format_velocity_packet(1.0, -2.5) == "v,1.0,-2.5"
    assert format_state_sync_packet(12, 3, 1, 0) == "s,12,3,1,0"
    assert format_ack_packet(12) == "a,12"
    assert format_event_packet(12, 2, -1) == "r,12,2,-1"


def test_is_newer_seq_uses_ring_order() -> None:
    assert is_newer_seq(1, None) is True
    assert is_newer_seq(13, 12) is True
    assert is_newer_seq(0, 255) is True
    assert is_newer_seq(12, 12) is False
    assert is_newer_seq(11, 12) is False
    assert is_newer_seq(255, 0) is False
