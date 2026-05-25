"""串口按行读取共享能力.

@file src/vision/uart_line_reader.py
"""


STATUS_NO_DATA = "no_data"
STATUS_READY = "ready"
STATUS_OVERFLOW = "overflow"
STATUS_ANY_ERROR = "any_error"
STATUS_READ_ERROR = "read_error"
STATUS_DECODE_ERROR = "decode_error"


class UartLineReader:
    """带固定输入上限的串口按行读取器."""

    def __init__(self, input_limit: int, discard_remainder_on_overflow: bool = False) -> None:
        self.input_limit = int(input_limit)
        self.discard_remainder_on_overflow = bool(discard_remainder_on_overflow)
        self.buffer = ""

    def clear(self) -> None:
        """清空当前缓存."""

        self.buffer = ""

    def read_available(self, uart) -> dict:
        """读取当前所有可用输入并拆成按行结果."""

        lines = []
        overflowed = False

        while True:
            try:
                available = uart.any()
            except Exception as exc:
                return self._build_result(lines, STATUS_ANY_ERROR, exc)
            if not available:
                if overflowed:
                    return self._build_result(lines, STATUS_OVERFLOW, None)
                if lines:
                    return self._build_result(lines, STATUS_READY, None)
                return self._build_result(lines, STATUS_NO_DATA, None)

            input_overflow = available > self.input_limit
            if input_overflow:
                available = self.input_limit

            try:
                chunk = uart.read(available)
                if chunk is None:
                    chunk = b""
                text = chunk.decode()
            except Exception as exc:
                if exc.__class__.__name__ == "UnicodeDecodeError":
                    return self._build_result(lines, STATUS_DECODE_ERROR, exc)
                return self._build_result(lines, STATUS_READ_ERROR, exc)

            self.buffer += text
            drained_lines, dropped_line, hard_overflow = self._drain_buffered_lines()
            lines.extend(drained_lines)
            overflowed = overflowed or dropped_line
            if hard_overflow:
                self.buffer = ""
                discard_status, discard_exc = self._discard_until_newline(uart)
                if discard_status is not None:
                    return self._build_result(lines, discard_status, discard_exc)
                overflowed = True
                continue
            if input_overflow:
                self.buffer = ""
                if self.discard_remainder_on_overflow:
                    discard_status, discard_exc = self._discard_pending_input(uart)
                    if discard_status is not None:
                        return self._build_result(lines, discard_status, discard_exc)
                return self._build_result(lines, STATUS_OVERFLOW, None)

    def _drain_buffered_lines(self):
        lines = []
        overflowed = False
        while True:
            if len(self.buffer) > self.input_limit:
                self.buffer = ""
                return lines, True, True
            idx = self.buffer.find("\n")
            if idx == -1:
                return lines, overflowed, False
            if idx > self.input_limit:
                self.buffer = self.buffer[idx + 1 :]
                overflowed = True
                continue
            line = self.buffer[:idx].rstrip("\r").strip()
            self.buffer = self.buffer[idx + 1 :]
            lines.append(line)

    def _discard_pending_input(self, uart):
        while True:
            try:
                pending = uart.any()
            except Exception as exc:
                return STATUS_ANY_ERROR, exc
            if not pending:
                return None, None
            if pending > self.input_limit:
                pending = self.input_limit
            try:
                uart.read(pending)
            except Exception as exc:
                return STATUS_READ_ERROR, exc

    def _discard_until_newline(self, uart):
        while True:
            try:
                pending = uart.any()
            except Exception as exc:
                return STATUS_ANY_ERROR, exc
            if not pending:
                return None, None
            if pending > self.input_limit:
                pending = self.input_limit
            try:
                chunk = uart.read(pending)
                if chunk is None:
                    chunk = b""
                text = chunk.decode()
            except Exception as exc:
                if exc.__class__.__name__ == "UnicodeDecodeError":
                    return STATUS_DECODE_ERROR, exc
                return STATUS_READ_ERROR, exc
            idx = text.find("\n")
            if idx == -1:
                continue
            self.buffer = text[idx + 1 :]
            return None, None

    def _build_result(self, lines, status: str, exception) -> dict:
        return {
            "lines": list(lines),
            "status": status,
            "exception": exception,
            "buffer": self.buffer,
        }
