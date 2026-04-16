"""辅车 UART3 速度控制协议输入测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from config import params as _params
from vision.assistant.control_protocol_input import (
    CONSUME_ACCEPTED,
    CONSUME_IGNORED,
    CONSUME_INVALID,
    ControlProtocolInput,
)


V_CMD_MAX = getattr(_params, "V_CMD_MAX")


class _FakeClock:
    def __init__(self, initial_ms: int = 0) -> None:
        self.now_ms = initial_ms

    def advance(self, delta_ms: int) -> None:
        self.now_ms += delta_ms

    def __call__(self) -> int:
        return self.now_ms


def test_accepts_single_speed_key_packet_and_updates_only_that_axis() -> None:
    clock = _FakeClock(123)
    control_input = ControlProtocolInput(validity_ms=50, now_ms=clock)

    assert control_input.consume("vx=10") == CONSUME_ACCEPTED

    control = control_input.get_active_control()
    assert control is not None
    assert (control.vx, control.vy, control.omega, control.timestamp_ms) == (
        10.0,
        0.0,
        0.0,
        123,
    )

    clock.advance(7)
    assert control_input.consume("w=30") == CONSUME_ACCEPTED

    control = control_input.get_active_control()
    assert control is not None
    assert (control.vx, control.vy, control.omega, control.timestamp_ms) == (
        10.0,
        0.0,
        30.0,
        130,
    )


def test_accepts_multi_key_speed_packet_and_refreshes_cached_control() -> None:
    clock = _FakeClock(5)
    control_input = ControlProtocolInput(validity_ms=100, now_ms=clock)

    assert control_input.consume("vx=1,vy=2,omega=3") == CONSUME_ACCEPTED
    clock.advance(8)
    assert control_input.consume("vy=5,w=6") == CONSUME_ACCEPTED

    control = control_input.get_active_control()
    assert control is not None
    assert (control.vx, control.vy, control.omega, control.timestamp_ms) == (
        1.0,
        5.0,
        6.0,
        13,
    )


def test_ignores_queries_and_non_velocity_commands() -> None:
    control_input = ControlProtocolInput(validity_ms=50, now_ms=lambda: 0)

    assert control_input.consume("?health") == CONSUME_IGNORED
    assert control_input.consume("reset") == CONSUME_IGNORED
    assert control_input.consume("x=1") == CONSUME_IGNORED
    assert control_input.consume("vx=1,x=2") == CONSUME_IGNORED
    assert control_input.get_active_control() is None


def test_cached_control_expires_after_validity_window() -> None:
    clock = _FakeClock(10)
    control_input = ControlProtocolInput(validity_ms=30, now_ms=clock)

    assert control_input.consume("vx=1") == CONSUME_ACCEPTED
    clock.advance(30)
    assert control_input.get_active_control() is not None
    clock.advance(1)

    assert control_input.get_active_control() is None


def test_rejects_duplicate_nan_and_out_of_range_speed_packets() -> None:
    control_input = ControlProtocolInput(validity_ms=50, now_ms=lambda: 100)

    assert control_input.consume("vx=1,vy=2,vx=4") == CONSUME_INVALID
    assert control_input.get_active_control() is None

    assert control_input.consume("vx=1,omega=3,w=4") == CONSUME_INVALID
    assert control_input.get_active_control() is None

    assert control_input.consume("vx=1,omega=bad") == CONSUME_INVALID
    assert control_input.get_active_control() is None

    assert control_input.consume("vx=nan") == CONSUME_INVALID
    assert control_input.get_active_control() is None

    assert control_input.consume("vx=1,omega=%s" % (V_CMD_MAX + 1.0)) == CONSUME_INVALID
    assert control_input.get_active_control() is None


def test_invalid_packet_does_not_pollute_previous_valid_cached_control() -> None:
    clock = _FakeClock(200)
    control_input = ControlProtocolInput(validity_ms=50, now_ms=clock)

    assert control_input.consume("vx=7,vy=8,omega=9") == CONSUME_ACCEPTED
    clock.advance(1)
    assert control_input.consume("vx=7,omega=bad") == CONSUME_INVALID

    control = control_input.get_active_control()
    assert control is not None
    assert (control.vx, control.vy, control.omega, control.timestamp_ms) == (
        7.0,
        8.0,
        9.0,
        200,
    )
