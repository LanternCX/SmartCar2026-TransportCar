"""! @brief transport 公开 API 测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.codec import encode_master_vision_task_sync_body, encode_velocity_body  # noqa: E402
from protocol.frame import encode_frame  # noqa: E402
from protocol.topic import (  # noqa: E402
    ROLE_MASTER,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_TASK_SYNC,
    UART6,
    UART8,
)
from protocol.transport import create_transport  # noqa: E402


class _FakeUart:
    def __init__(self, incoming=b"") -> None:
        self._incoming = bytearray(incoming)
        self.messages = []
        self.read_sizes = []
        self.any_calls = 0

    def any(self) -> int:
        self.any_calls += 1
        return len(self._incoming)

    def read(self, size):
        self.read_sizes.append(int(size))
        chunk = bytes(self._incoming[:size])
        del self._incoming[:size]
        return chunk

    def write(self, data):
        self.messages.append(bytes(data))
        return len(data)


class _ManualClock:
    def __init__(self, value=0) -> None:
        self.value = int(value)

    def __call__(self):
        return int(self.value)


def test_udp_write_copies_body_and_overwrites_same_topic_slot() -> None:
    clock = _ManualClock(0)
    uart8 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart8=uart8, now_ms=clock)
    body = bytearray(encode_velocity_body(1.0, -2.0, 0.5, True))

    assert (
        transport.udp_write(UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY, body)
        == "accepted"
    )
    body[0] = 0
    assert (
        transport.udp_write(
            UART8,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            encode_velocity_body(0.25, 0.5, 0.0, False),
        )
        == "overwritten"
    )

    transport.poll_tx()

    assert uart8.messages == [
        encode_frame(
            0x01,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            0,
            encode_velocity_body(0.25, 0.5, 0.0, False),
        )
    ]


def test_udp_read_copies_out_body_without_consuming_latest_value() -> None:
    body = encode_velocity_body(0.08, -0.04, 0.0, False)
    uart6 = _FakeUart(incoming=encode_frame(0x01, TOPIC_LOCAL_VISION_VELOCITY, 0, body))
    transport = create_transport(ROLE_MASTER, uart6=uart6)
    out_body = bytearray(7)

    transport.poll_rx()

    assert transport.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, out_body) == "ok"
    assert bytes(out_body) == body
    out_body_2 = bytearray(7)
    assert transport.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, out_body_2) == "ok"
    assert bytes(out_body_2) == body


def test_tcp_write_busy_and_delivery_lifecycle() -> None:
    clock = _ManualClock(0)
    uart6 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart6=uart6, now_ms=clock)
    body = encode_master_vision_task_sync_body(7, 1, 3, 0)

    assert transport.tcp_write(UART6, TOPIC_MASTER_VISION_TASK_SYNC, body) == "accepted"
    assert transport.tcp_delivery(UART6, TOPIC_MASTER_VISION_TASK_SYNC) == "pending"
    assert transport.tcp_write(UART6, TOPIC_MASTER_VISION_TASK_SYNC, body) == "overwritten"

    transport.poll_tx()
    assert transport.tcp_write(UART6, TOPIC_MASTER_VISION_TASK_SYNC, body) == "dropped_busy"
    ack_frame = encode_frame(0x03, TOPIC_MASTER_VISION_TASK_SYNC, 0, b"")
    uart6._incoming.extend(ack_frame)
    transport.poll_rx()

    assert transport.tcp_delivery(UART6, TOPIC_MASTER_VISION_TASK_SYNC) == "delivered"


def test_diagnostics_and_delivery_do_not_write_frames() -> None:
    uart8 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart8=uart8)

    assert transport.tcp_delivery(UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY) == "invalid"
    assert uart8.messages == []


def test_udp_write_returns_dropped_priority_when_ack_is_pending() -> None:
    uart8 = _FakeUart(
        incoming=encode_frame(0x02, 0x21, 0x22, bytes([6, 0, 9]))
    )
    transport = create_transport(ROLE_MASTER, uart8=uart8)

    transport.poll_rx()

    assert (
        transport.udp_write(
            UART8,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            encode_velocity_body(0.25, 0.5, 0.0, False),
        )
        == "dropped_priority"
    )


def test_tcp_write_returns_dropped_priority_when_ack_is_pending() -> None:
    uart6 = _FakeUart(
        incoming=encode_frame(0x02, 0x12, 0x10, bytes([1, 2, 3, 4]))
    )
    transport = create_transport(ROLE_MASTER, uart6=uart6)

    transport.poll_rx()

    assert (
        transport.tcp_write(
            UART6,
            TOPIC_MASTER_VISION_TASK_SYNC,
            encode_master_vision_task_sync_body(7, 1, 3, 0),
        )
        == "dropped_priority"
    )


def test_udp_write_still_accepts_latest_value_while_tcp_waits_for_ack() -> None:
    clock = _ManualClock(0)
    uart6 = _FakeUart()
    uart8 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8, now_ms=clock)

    assert (
        transport.tcp_write(
            UART6,
            TOPIC_MASTER_VISION_TASK_SYNC,
            encode_master_vision_task_sync_body(7, 1, 3, 0),
        )
        == "accepted"
    )
    transport.poll_tx()

    assert (
        transport.udp_write(
            UART8,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            encode_velocity_body(0.25, 0.5, 0.0, False),
        )
        == "accepted"
    )
