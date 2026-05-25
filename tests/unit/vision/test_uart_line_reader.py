"""串口按行读取共享能力测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.uart_line_reader import (  # noqa: E402
    STATUS_ANY_ERROR,
    STATUS_DECODE_ERROR,
    STATUS_OVERFLOW,
    STATUS_READ_ERROR,
    STATUS_READY,
    UartLineReader,
)


class _FakeUart:
    def __init__(self, payload: bytes = b"", any_limit: int | None = None) -> None:
        self._buffer = bytes(payload)
        self.read_sizes = []
        self.any_error = None
        self.read_error = None
        self.any_limit = any_limit

    def any(self) -> int:
        if self.any_error is not None:
            raise self.any_error
        size = len(self._buffer)
        if self.any_limit is None:
            return size
        return min(size, int(self.any_limit))

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        self.read_sizes.append(int(size))
        chunk = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return chunk


def test_uart_line_reader_returns_complete_lines_and_preserves_half_line() -> None:
    reader = UartLineReader(input_limit=16)
    uart = _FakeUart(b"v,1,2\nhalf")

    first = reader.read_available(uart)
    uart._buffer = b"_line\n"
    second = reader.read_available(uart)

    assert first["status"] == STATUS_READY
    assert first["lines"] == ["v,1,2"]
    assert first["buffer"] == "half"
    assert second["status"] == STATUS_READY
    assert second["lines"] == ["half_line"]
    assert second["buffer"] == ""


def test_uart_line_reader_drops_overlong_line_without_blocking_following_line() -> None:
    reader = UartLineReader(input_limit=8)
    uart = _FakeUart(b"ok\nxxxxxxxxxx\nnext\n", any_limit=4)

    result = reader.read_available(uart)

    assert result["status"] == STATUS_OVERFLOW
    assert result["lines"] == ["ok", "next"]
    assert result["buffer"] == ""


def test_uart_line_reader_discards_overflow_tail_when_requested() -> None:
    reader = UartLineReader(input_limit=16, discard_remainder_on_overflow=True)
    uart = _FakeUart(b"x\ns,12,1,1,0\n" + (b"z" * 40))

    result = reader.read_available(uart)

    assert result["status"] == STATUS_OVERFLOW
    assert result["lines"] == ["x", "s,12,1,1,0"]
    assert result["buffer"] == ""
    assert uart._buffer == b""
    assert uart.read_sizes
    assert max(uart.read_sizes) <= 16


def test_uart_line_reader_records_decode_failure() -> None:
    reader = UartLineReader(input_limit=16)
    uart = _FakeUart(b"\xff\n")

    result = reader.read_available(uart)

    assert result["status"] == STATUS_DECODE_ERROR
    assert result["lines"] == []
    assert result["exception"] is not None


def test_uart_line_reader_records_any_and_read_failures() -> None:
    any_reader = UartLineReader(input_limit=16)
    any_uart = _FakeUart()
    any_uart.any_error = RuntimeError("any boom")

    read_reader = UartLineReader(input_limit=16)
    read_uart = _FakeUart(b"v,1,2\n")
    read_uart.read_error = RuntimeError("read boom")

    any_result = any_reader.read_available(any_uart)
    read_result = read_reader.read_available(read_uart)

    assert any_result["status"] == STATUS_ANY_ERROR
    assert str(any_result["exception"]) == "any boom"
    assert read_result["status"] == STATUS_READ_ERROR
    assert str(read_result["exception"]) == "read boom"
