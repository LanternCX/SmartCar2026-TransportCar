"""辅车双路速度源状态测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.assistant.velocity_packet import (
    CONSUME_ACCEPTED,
    CONSUME_IGNORED,
    CONSUME_INVALID,
    parse_velocity_fragments,
)


def test_parse_velocity_fragments_accepts_and_fills_default_axes() -> None:
    consume_result, parsed = parse_velocity_fragments(["vx=12", "vy=-4"])

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 12.0, "vy": -4.0, "omega": 0.0}

    consume_result, parsed = parse_velocity_fragments(["vy=8", "omega=1.5", "vx=6.5"])

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 6.5, "vy": 8.0, "omega": 1.5}


def test_parse_velocity_fragments_accepts_single_axis_packet() -> None:
    consume_result, parsed = parse_velocity_fragments(["vx=-4.6"])

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": -4.6, "vy": 0.0, "omega": 0.0}


def test_parse_velocity_fragments_ignores_empty_input() -> None:
    consume_result, parsed = parse_velocity_fragments([])

    assert consume_result == CONSUME_IGNORED
    assert parsed is None


def test_parse_velocity_fragments_accepts_variants_with_same_rules() -> None:
    consume_result, parsed = parse_velocity_fragments(["vy=2", "vx=1"])

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 2.0, "omega": 0.0}

    consume_result, parsed = parse_velocity_fragments(["vx=1", " vy=2", " w=-3"])

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 2.0, "omega": -3.0}


def test_parse_velocity_fragments_does_not_add_extra_timeout_semantics() -> None:
    consume_result, parsed = parse_velocity_fragments(["vx=1"])

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 0.0, "omega": 0.0}


def test_parse_velocity_fragments_rejects_duplicate_nan_and_bad_packets() -> None:
    consume_result, parsed = parse_velocity_fragments(["vx=1", "vy=2", "vx=3"])
    assert consume_result == CONSUME_INVALID
    assert parsed is None

    consume_result, parsed = parse_velocity_fragments(["vx=1", "vy=nan"])
    assert consume_result == CONSUME_INVALID
    assert parsed is None

    consume_result, parsed = parse_velocity_fragments(["vx=1", "vy=bad"])
    assert consume_result == CONSUME_INVALID
    assert parsed is None

    consume_result, parsed = parse_velocity_fragments(["VX=1", "vy=2"])
    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 2.0, "omega": 0.0}

    consume_result, parsed = parse_velocity_fragments(["vx=1", "VY=2"])
    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 2.0, "omega": 0.0}

    consume_result, parsed = parse_velocity_fragments(["vx=1", "foo=2"])
    assert consume_result == CONSUME_IGNORED
    assert parsed is None

    consume_result, parsed = parse_velocity_fragments(["vx=1", "", "vy=2"])
    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": 1.0, "vy": 2.0, "omega": 0.0}


def test_invalid_packet_does_not_produce_new_velocity_vector() -> None:
    consume_result, parsed = parse_velocity_fragments(["vx=7", "vy=bad"])

    assert consume_result == CONSUME_INVALID
    assert parsed is None


def test_parse_velocity_fragments_returns_plain_velocity_dict() -> None:
    consume_result, parsed = parse_velocity_fragments(["vx=-2", "vy=3", "omega=4"])

    assert consume_result == CONSUME_ACCEPTED
    assert parsed == {"vx": -2.0, "vy": 3.0, "omega": 4.0}
