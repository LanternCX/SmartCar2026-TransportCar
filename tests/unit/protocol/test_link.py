"""! @brief 可靠串口写出辅助测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.link import (  # noqa: E402
    should_resend,
    write_data_line,
    write_reliable_line,
)


class _FakeUart:
    def __init__(self) -> None:
        self.messages = []
        self.return_value = None

    def write(self, text) -> int | None:
        self.messages.append(text)
        if self.return_value is None:
            return len(text)
        return self.return_value


def test_should_resend_allows_first_send_and_interval_boundary() -> None:
    assert should_resend(100, None, 20) is True
    assert should_resend(119, 100, 20) is False
    assert should_resend(120, 100, 20) is True


def test_should_resend_handles_wrapped_tick_difference() -> None:
    assert should_resend(5, 250, 10) is True


def test_write_reliable_line_writes_without_delay_hook() -> None:
    uart = _FakeUart()

    wrote_all = write_reliable_line(uart, "a,12")

    assert uart.messages == ["a,12\r\n"]
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


def test_write_line_reports_timeout_when_uart_write_returns_none() -> None:
    uart = _FakeUart()
    uart.write = lambda text: (uart.messages.append(text), None)[1]

    assert write_reliable_line(uart, "a,12") is False
