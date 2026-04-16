"""辅车 UART6 本地视觉输入测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.assistant.vision_input import (
    CONSUME_ACCEPTED,
    CONSUME_IGNORED,
    CONSUME_INVALID,
    AssistantVisionInput,
)


class _FakeClock:
    def __init__(self, initial_ms: int = 0) -> None:
        self.now_ms = initial_ms

    def advance(self, delta_ms: int) -> None:
        self.now_ms += delta_ms

    def __call__(self) -> int:
        return self.now_ms


def test_accepts_uart6_vision_packet_and_refreshes_cached_observation() -> None:
    clock = _FakeClock(123)
    vision_input = AssistantVisionInput(validity_ms=50, now_ms=clock)

    assert vision_input.consume("UART6", "x=12,y=-4") == CONSUME_ACCEPTED

    observation = vision_input.get_active_observation()
    assert observation is not None
    assert (observation.x, observation.y, observation.timestamp_ms) == (12.0, -4.0, 123)

    clock.advance(7)
    assert vision_input.consume("UART6", "x=6.5,y=8") == CONSUME_ACCEPTED

    observation = vision_input.get_active_observation()
    assert observation is not None
    assert (observation.x, observation.y, observation.timestamp_ms) == (6.5, 8.0, 130)
    assert vision_input.get_observation_age_ms() == 0


def test_ignores_non_uart6_and_non_vision_lines() -> None:
    vision_input = AssistantVisionInput(validity_ms=50, now_ms=lambda: 0)

    assert vision_input.consume("UART3", "x=1,y=2") == CONSUME_IGNORED
    assert vision_input.consume("UART6", "?vision") == CONSUME_IGNORED
    assert vision_input.consume("UART6", "vx=1") == CONSUME_IGNORED
    assert vision_input.consume("UART6", "x=1") == CONSUME_IGNORED
    assert vision_input.get_active_observation() is None


def test_rejects_protocol_variants_outside_exact_x_then_y_format() -> None:
    vision_input = AssistantVisionInput(validity_ms=50, now_ms=lambda: 0)

    assert vision_input.consume("UART6", "y=2,x=1") == CONSUME_INVALID
    assert vision_input.consume("UART6", "X=1,y=2") == CONSUME_INVALID
    assert vision_input.consume("UART6", "x=1,Y=2") == CONSUME_INVALID
    assert vision_input.consume("UART6", "x=1,y=2,z=3") == CONSUME_INVALID
    assert vision_input.consume("UART6", "x=1, y=2") == CONSUME_INVALID
    assert vision_input.get_active_observation() is None


def test_cached_observation_expires_after_validity_window() -> None:
    clock = _FakeClock(10)
    vision_input = AssistantVisionInput(validity_ms=30, now_ms=clock)

    assert vision_input.consume("UART6", "x=1,y=2") == CONSUME_ACCEPTED
    clock.advance(30)
    assert vision_input.get_active_observation() is not None
    assert vision_input.get_observation_age_ms() == 30
    clock.advance(1)

    assert vision_input.get_active_observation() is None
    assert vision_input.get_observation_age_ms() is None


def test_rejects_duplicate_nan_and_malformed_packets() -> None:
    vision_input = AssistantVisionInput(validity_ms=50, now_ms=lambda: 100)

    assert vision_input.consume("UART6", "x=1,y=2,x=3") == CONSUME_INVALID
    assert vision_input.get_active_observation() is None

    assert vision_input.consume("UART6", "x=1,y=nan") == CONSUME_INVALID
    assert vision_input.get_active_observation() is None

    assert vision_input.consume("UART6", "x=1,y=bad") == CONSUME_INVALID
    assert vision_input.get_active_observation() is None

    assert vision_input.consume("UART6", "x=1,,y=2") == CONSUME_INVALID
    assert vision_input.get_active_observation() is None


def test_invalid_packet_does_not_pollute_previous_valid_cached_observation() -> None:
    clock = _FakeClock(200)
    vision_input = AssistantVisionInput(validity_ms=50, now_ms=clock)

    assert vision_input.consume("UART6", "x=7,y=8") == CONSUME_ACCEPTED
    clock.advance(1)
    assert vision_input.consume("UART6", "x=7,y=bad") == CONSUME_INVALID

    observation = vision_input.get_active_observation()
    assert observation is not None
    assert (observation.x, observation.y, observation.timestamp_ms) == (7.0, 8.0, 200)


def test_snapshot_only_exposes_observation_and_age() -> None:
    clock = _FakeClock(50)
    vision_input = AssistantVisionInput(validity_ms=100, now_ms=clock)

    assert vision_input.snapshot() == {
        "valid": False,
        "x": None,
        "y": None,
        "timestamp_ms": None,
        "age_ms": None,
    }

    assert vision_input.consume("UART6", "x=-2,y=3") == CONSUME_ACCEPTED
    clock.advance(5)

    assert vision_input.snapshot() == {
        "valid": True,
        "x": -2.0,
        "y": 3.0,
        "timestamp_ms": 50,
        "age_ms": 5,
    }


def test_get_active_observation_returns_copy_instead_of_internal_cache() -> None:
    clock = _FakeClock(80)
    vision_input = AssistantVisionInput(validity_ms=100, now_ms=clock)

    assert vision_input.consume("UART6", "x=4,y=5") == CONSUME_ACCEPTED

    observation = vision_input.get_active_observation()
    assert observation is not None
    observation.x = 999.0
    observation.y = -999.0
    observation.timestamp_ms = 0

    fresh_observation = vision_input.get_active_observation()
    assert fresh_observation is not None
    assert (
        fresh_observation.x,
        fresh_observation.y,
        fresh_observation.timestamp_ms,
    ) == (
        4.0,
        5.0,
        80,
    )
