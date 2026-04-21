"""辅车共享速度包解析测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.assistant.velocity_packet import (
    CONSUME_ACCEPTED,
    CONSUME_IGNORED,
    CONSUME_INVALID,
    split_velocity_line,
)


def test_split_velocity_line_accepts_same_velocity_semantics() -> None:
    consume_result, parsed, passthrough = split_velocity_line(
        "vy=0.25, omega=-1.5, vx=-0.5"
    )

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": -0.5, "vy": 0.25, "omega": -1.5}
    assert passthrough is None

    consume_result, parsed, passthrough = split_velocity_line("vx=1")

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 0.0, "omega": 0.0}
    assert passthrough is None


def test_split_velocity_line_separates_passthrough_fragments() -> None:
    consume_result, parsed, passthrough = split_velocity_line(
        "vx=1.0,x=12.0,angle=45.0"
    )

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 0.0, "omega": 0.0}
    assert passthrough == "x=12.0,angle=45.0"

    consume_result, parsed, passthrough = split_velocity_line("?health")

    assert consume_result == CONSUME_IGNORED
    assert parsed is None
    assert passthrough == "?health"


def test_split_velocity_line_rejects_duplicate_and_bad_values() -> None:
    consume_result, parsed, passthrough = split_velocity_line("vx=1,vy=2,vx=3")

    assert consume_result == CONSUME_INVALID
    assert parsed is None
    assert passthrough is None

    consume_result, parsed, passthrough = split_velocity_line("vx=1,vy=bad")

    assert consume_result == CONSUME_INVALID
    assert parsed is None
    assert passthrough is None
