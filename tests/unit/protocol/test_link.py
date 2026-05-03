"""! @brief 可靠串口写出辅助测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from config import params as _params  # noqa: E402
from protocol.link import (  # noqa: E402
    should_resend,
    write_data_line,
    write_reliable_line,
)


class _FakeUart:
    def __init__(self) -> None:
        self.messages = []
        self.return_value = None

    def write(self, text) -> None:
        self.messages.append(text)
        return self.return_value


def test_should_resend_allows_first_send_and_interval_boundary() -> None:
    assert should_resend(100, None, 20) is True
    assert should_resend(119, 100, 20) is False
    assert should_resend(120, 100, 20) is True


def test_should_resend_handles_wrapped_tick_difference() -> None:
    assert should_resend(5, 250, 10) is True


def test_write_reliable_line_uses_configured_delay_around_write() -> None:
    uart = _FakeUart()
    calls = []

    wrote_all = write_reliable_line(uart, "a,12", sleep_fn=lambda delay_ms: calls.append(delay_ms))

    assert uart.messages == ["a,12\r\n"]
    assert calls == [
        _params.RELIABLE_PACKET_SEND_DELAY_MS,
        _params.RELIABLE_PACKET_SEND_DELAY_MS,
    ]
    assert wrote_all is True


def test_write_data_line_writes_without_reliable_delay() -> None:
    uart = _FakeUart()

    wrote_all = write_data_line(uart, "v,1,2")

    assert uart.messages == ["v,1,2\r\n"]
    assert wrote_all is True


def test_write_line_reports_incomplete_write() -> None:
    uart = _FakeUart()
    uart.return_value = 0

    assert write_data_line(uart, "v,1,2") is False
