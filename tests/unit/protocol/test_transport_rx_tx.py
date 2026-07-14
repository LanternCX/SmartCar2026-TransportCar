"""! @brief transport RX/TX 调度测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.codec import encode_master_vision_task_sync_body, encode_velocity_body  # noqa: E402
from protocol.frame import FRAME_SIZE, encode_frame  # noqa: E402
from protocol.topic import (  # noqa: E402
    ROLE_MASTER,
    TOPIC_ASSISTANT_EVENT_REPORT,
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
        self.any_calls = 0
        self.read_calls = 0
        self.read_sizes = []

    def any(self):
        self.any_calls += 1
        return len(self._incoming)

    def read(self, size):
        self.read_calls += 1
        self.read_sizes.append(int(size))
        chunk = bytes(self._incoming[:size])
        del self._incoming[:size]
        return chunk

    def write(self, data):
        self.messages.append(bytes(data))
        return len(data)

    def push(self, data):
        self._incoming.extend(bytes(data))


class _ManualClock:
    def __init__(self, value=0) -> None:
        self.value = int(value)

    def advance(self, delta):
        self.value += int(delta)

    def __call__(self):
        return int(self.value)


def test_poll_rx_limits_first_read_when_input_exceeds_limit() -> None:
    valid_frame = encode_frame(
        0x01, TOPIC_LOCAL_VISION_VELOCITY, 0, encode_velocity_body(0.08, -0.04, 0.0, False)
    )
    uart6 = _FakeUart(incoming=valid_frame + (b"\x99" * (FRAME_SIZE * 4)))
    uart8 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8)

    transport.poll_rx()

    assert uart6.read_calls >= 1
    assert uart6.read_sizes[0] == 32
    out_body = bytearray(7)
    assert transport.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, out_body) == "ok"


def test_poll_rx_finds_valid_udp_frame_after_leading_noise() -> None:
    latest_body = encode_velocity_body(0.03, 0.0, 0.0, False)
    uart6 = _FakeUart(
        incoming=(
            b"\x99"
            + encode_frame(0x01, TOPIC_LOCAL_VISION_VELOCITY, 0, latest_body)
        )
    )
    transport = create_transport(ROLE_MASTER, uart6=uart6)

    transport.poll_rx()

    out_body = bytearray(7)
    assert transport.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, out_body) == "ok"
    assert bytes(out_body) == latest_body


def test_poll_rx_skips_crc_invalid_false_udp_frame_after_lost_byte() -> None:
    latest_body = encode_velocity_body(0.03, 0.0, 0.0, False)
    uart6 = _FakeUart(
        incoming=(
            b"\x01"
            + encode_frame(0x01, TOPIC_LOCAL_VISION_VELOCITY, 0, latest_body)
        )
    )
    transport = create_transport(ROLE_MASTER, uart6=uart6)

    transport.poll_rx()

    out_body = bytearray(7)
    assert transport.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, out_body) == "ok"
    assert bytes(out_body) == latest_body


def test_poll_rx_skips_crc_invalid_false_ack_frame_after_lost_byte() -> None:
    body = bytes([6, 0, 9])
    uart8 = _FakeUart(
        incoming=(
            b"\x03"
            + encode_frame(0x02, TOPIC_ASSISTANT_EVENT_REPORT, 0x22, body)
        )
    )
    transport = create_transport(ROLE_MASTER, uart8=uart8)

    transport.poll_rx()

    out_body = bytearray(3)
    assert transport.tcp_read(UART8, TOPIC_ASSISTANT_EVENT_REPORT, out_body) == "ok"
    assert bytes(out_body) == body


def test_poll_rx_requests_each_port_once_per_cycle_when_input_is_normal() -> None:
    uart6 = _FakeUart(
        incoming=encode_frame(
            0x01, TOPIC_LOCAL_VISION_VELOCITY, 0, encode_velocity_body(0.08, -0.04, 0.0, False)
        )
    )
    uart8 = _FakeUart(
        incoming=encode_frame(
            0x01,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            0,
            encode_velocity_body(0.5, 0.25, 0.0, False),
        )
    )
    transport = create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8)

    transport.poll_rx()

    assert uart6.any_calls == 1
    assert uart6.read_calls == 1
    assert uart8.any_calls == 1
    assert uart8.read_calls == 1


def test_poll_tx_allows_only_one_frame_per_call_globally() -> None:
    clock = _ManualClock(0)
    uart6 = _FakeUart()
    uart8 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8, now_ms=clock)

    transport.tcp_write(
        UART6,
        TOPIC_MASTER_VISION_TASK_SYNC,
        encode_master_vision_task_sync_body(1, 2, 3, 4),
    )
    transport.udp_write(
        UART8,
        TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
        encode_velocity_body(1.0, 0.0, 0.0, False),
    )

    transport.poll_tx()

    assert len(uart6.messages) + len(uart8.messages) == 1


def test_ack_frame_has_higher_priority_than_udp() -> None:
    clock = _ManualClock(0)
    body = bytes([6, 0, 9])
    frame = encode_frame(0x02, TOPIC_ASSISTANT_EVENT_REPORT, 0x22, body)
    uart8 = _FakeUart(incoming=frame)
    transport = create_transport(ROLE_MASTER, uart8=uart8, now_ms=clock)

    transport.poll_rx()
    transport.udp_write(
        UART8,
        TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
        encode_velocity_body(0.5, 0.25, 0.0, False),
    )
    transport.poll_tx()

    assert uart8.messages == [encode_frame(0x03, TOPIC_ASSISTANT_EVENT_REPORT, 0x22, b"")]


def test_poll_rx_reassembles_fragmented_udp_frame_across_cycles() -> None:
    body = encode_velocity_body(0.08, -0.04, 0.0, False)
    frame = encode_frame(0x01, TOPIC_LOCAL_VISION_VELOCITY, 0, body)
    uart6 = _FakeUart(incoming=frame[:5])
    transport = create_transport(ROLE_MASTER, uart6=uart6)

    transport.poll_rx()

    out_body = bytearray(7)
    assert transport.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, out_body) == "empty"

    uart6.push(frame[5:])
    transport.poll_rx()

    assert transport.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, out_body) == "ok"
    assert out_body == body


def test_poll_rx_reassembles_fragmented_ack_frame_across_cycles() -> None:
    clock = _ManualClock(0)
    body = encode_master_vision_task_sync_body(7, 1, 3, 0)
    uart6 = _FakeUart()
    transport = create_transport(ROLE_MASTER, uart6=uart6, now_ms=clock)

    assert transport.tcp_write(UART6, TOPIC_MASTER_VISION_TASK_SYNC, body) == "accepted"
    transport.poll_tx()
    ack_frame = encode_frame(0x03, TOPIC_MASTER_VISION_TASK_SYNC, 0, b"")

    uart6.push(ack_frame[:4])
    transport.poll_rx()
    assert transport.tcp_delivery(UART6, TOPIC_MASTER_VISION_TASK_SYNC) == "pending"

    uart6.push(ack_frame[4:])
    transport.poll_rx()
    assert transport.tcp_delivery(UART6, TOPIC_MASTER_VISION_TASK_SYNC) == "delivered"
