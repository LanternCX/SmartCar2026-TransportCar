"""辅车共享速度包解析测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.velocity_packet import (  # noqa: E402
    CONSUME_ACCEPTED,
    CONSUME_IGNORED,
    CONSUME_INVALID,
    split_velocity_line,
)


def test_split_velocity_line_accepts_velocity_short_packet_with_omega() -> None:
    consume_result, parsed = split_velocity_line("v,1.25,-0.5,0.75")

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.25, "vy": -0.5, "omega": 0.75, "has_omega": True}


def test_split_velocity_line_accepts_velocity_short_packet_without_omega() -> None:
    consume_result, parsed = split_velocity_line("v,1.25,-0.5")

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.25, "vy": -0.5, "omega": 0.0, "has_omega": False}


def test_split_velocity_line_rejects_non_short_packet_velocity_text() -> None:
    consume_result, parsed = split_velocity_line("vx=1,vy=2")

    assert consume_result == CONSUME_IGNORED
    assert parsed is None


def test_split_velocity_line_rejects_invalid_velocity_short_packet() -> None:
    consume_result, parsed = split_velocity_line("v,1,bad")

    assert consume_result == CONSUME_INVALID
    assert parsed is None


def test_split_velocity_line_ignores_non_velocity_short_packet() -> None:
    consume_result, parsed = split_velocity_line("s,12,3,1,0")

    assert consume_result == CONSUME_IGNORED
    assert parsed is None


def test_split_velocity_line_clamps_each_axis_with_shared_limit() -> None:
    consume_result, parsed = split_velocity_line("v,2000,-2000,3000")

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1000.0, "vy": -1000.0, "omega": 1000.0, "has_omega": True}
