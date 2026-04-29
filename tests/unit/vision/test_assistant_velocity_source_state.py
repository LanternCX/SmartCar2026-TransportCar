"""辅车速度短包源状态测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.assistant.velocity_packet import (  # noqa: E402
    CONSUME_ACCEPTED,
    CONSUME_IGNORED,
    CONSUME_INVALID,
    split_velocity_line,
)


def test_velocity_short_packet_fills_default_omega() -> None:
    consume_result, parsed = split_velocity_line("v,12,-4")

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 12.0, "vy": -4.0, "omega": 0.0, "has_omega": False}


def test_velocity_short_packet_preserves_omega_presence() -> None:
    consume_result, parsed = split_velocity_line("v,6.5,8,1.5")

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 6.5, "vy": 8.0, "omega": 1.5, "has_omega": True}


def test_empty_input_is_ignored() -> None:
    consume_result, parsed = split_velocity_line("")

    assert consume_result == CONSUME_IGNORED
    assert parsed is None


def test_invalid_velocity_short_packet_does_not_produce_velocity_vector() -> None:
    consume_result, parsed = split_velocity_line("v,7,bad")

    assert consume_result == CONSUME_INVALID
    assert parsed is None


def test_non_short_packet_velocity_text_is_not_formal_velocity_input() -> None:
    consume_result, parsed = split_velocity_line("vx=-2,vy=3,omega=4")

    assert consume_result == CONSUME_IGNORED
    assert parsed is None
