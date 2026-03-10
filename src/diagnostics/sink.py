"""日志 sink 实现.

提供直接写 UART 的 sink 和按等级保留的环形缓冲 sink.
"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Protocol

    class UartLike(Protocol):
        """最小 UART 写接口."""

        def write(self, text: str) -> None:
            """写出字符串数据."""
            ...
else:

    class UartLike:
        """最小 UART 写接口."""

        def write(self, text: str) -> None:
            """写出字符串数据."""
            raise NotImplementedError


class UartSink:
    """将格式化日志立即写到 UART 风格对象."""

    def __init__(self, uart: UartLike) -> None:
        self._uart = uart

    def write(self, text: str) -> None:
        """立即写出日志文本."""
        self._uart.write(text)


class RingBufferSink:
    """固定容量的日志缓冲, 满时优先保留高等级日志."""

    def __init__(self, max_lines: int) -> None:
        if max_lines <= 0:
            raise ValueError("max_lines must be > 0")
        self._max_lines = max_lines
        self._slots: "list[tuple[int, int, str] | None]" = [None] * max_lines
        self._size = 0
        self._next_sequence = 0

    def write(self, text: str) -> None:
        """兼容基础 sink 协议, 未知等级按最低优先级处理."""
        self.write_record(0, text)

    def write_record(self, level: int, text: str) -> None:
        """写入一条带等级的日志记录."""
        sequence = self._next_sequence
        self._next_sequence += 1

        if self._size < self._max_lines:
            self._slots[self._size] = (level, sequence, text)
            self._size += 1
            return

        first_item = self._slots[0]
        if first_item is None:
            return

        lowest_level = first_item[0]
        replace_index = 0
        oldest_sequence = first_item[1]

        for index in range(1, self._max_lines):
            current = self._slots[index]
            if current is None:
                continue
            current_level = current[0]
            current_sequence = current[1]
            if current_level < lowest_level:
                lowest_level = current_level
                replace_index = index
                oldest_sequence = current_sequence
            elif current_level == lowest_level and current_sequence < oldest_sequence:
                replace_index = index
                oldest_sequence = current_sequence

        if level < lowest_level:
            return

        self._slots[replace_index] = (level, sequence, text)

    def snapshot(self) -> "list[str]":
        """返回当前缓冲区中的日志文本快照."""
        items = []
        for index in range(self._size):
            item = self._slots[index]
            if item is not None:
                items.append(item)

        items.sort(key=lambda item: item[1])
        return [item[2] for item in items]
