"""! @brief transport 可靠通信测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.frame import encode_frame  # noqa: E402
from protocol.topic import (  # noqa: E402
    ROLE_MASTER,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_MASTER_VISION_TASK_SYNC,
    UART6,
    UART8,
)
from protocol.transport import create_transport  # noqa: E402


class _FakeUart:
    def __init__(self, incoming=b"") -> None:
        self._incoming = bytearray(incoming)
        self.messages = []

    def any(self):
        return len(self._incoming)

    def read(self, size):
        chunk = bytes(self._incoming[:size])
        del self._incoming[:size]
        return chunk

    def write(self, data):
        self.messages.append(bytes(data))
        return len(data)


class _ManualClock:
    def __init__(self, value=0) -> None:
        self.value = int(value)

    def advance(self, delta):
        self.value += int(delta)

    def __call__(self):
        return int(self.value)


def test_tcp_resends_same_seq_until_ack() -> None:
    clock = _ManualClock(0)
    uart6 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart6=uart6, now_ms=clock)

    assert transport.tcp(UART6).write(TOPIC_MASTER_VISION_TASK_SYNC, bytes([1, 2, 3, 4, 5])) == "accepted"
    transport.poll_tx()
    first = uart6.messages[-1]

    clock.advance(100)
    transport.poll_tx()
    assert uart6.messages == [first]

    clock.advance(50)
    transport.poll_tx()
    assert uart6.messages == [first, first]


def test_duplicate_tcp_frame_is_acked_but_not_redelivered() -> None:
    body = bytes([6, 0, 9])
    frame = encode_frame(0x02, TOPIC_ASSISTANT_EVENT_REPORT, 0x22, body)
    uart8 = _FakeUart(incoming=frame + frame)
    transport = create_transport(ROLE_MASTER, uart8=uart8)
    out_body = bytearray(3)

    transport.poll_rx()

    assert transport.tcp(UART8).read(TOPIC_ASSISTANT_EVENT_REPORT, out_body) == "ok"
    assert bytes(out_body) == body
    assert transport.tcp(UART8).read(TOPIC_ASSISTANT_EVENT_REPORT, bytearray(3)) == "empty"

    transport.poll_tx()

    assert uart8.messages == [encode_frame(0x03, TOPIC_ASSISTANT_EVENT_REPORT, 0x22, b"")]


def test_active_seq_is_unique_per_port_until_ack() -> None:
    clock = _ManualClock(0)
    uart6 = _FakeUart()
    uart8 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8, now_ms=clock)

    assert transport.tcp(UART6).write(TOPIC_MASTER_VISION_TASK_SYNC, bytes([1, 2, 3, 4, 5])) == "accepted"
    assert transport.tcp(UART6).write(TOPIC_MASTER_VISION_TASK_SYNC, bytes([5, 4, 3, 2, 1])) == "overwritten"
    assert transport.tcp(UART8).write(TOPIC_ASSISTANT_STATE_SYNC, bytes([2, 1, 0, 0])) == "accepted"

    transport.poll_tx()
    assert transport.tcp(UART6).write(TOPIC_MASTER_VISION_TASK_SYNC, bytes([1, 2, 3, 4, 5])) == "dropped_busy"
    transport.poll_tx()

    assert len(uart6.messages) + len(uart8.messages) == 2
