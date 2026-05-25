"""可靠短包共享通道测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.reliable_channel import ReliableChannel  # noqa: E402


class _ManualNowMs:
    def __init__(self, value: int = 0) -> None:
        self.value = int(value)

    def __call__(self) -> int:
        return int(self.value)


def test_reliable_channel_allows_first_send_without_history() -> None:
    clock = _ManualNowMs(100)
    channel = ReliableChannel(now_ms=clock, resend_interval_ms=20)

    assert channel.should_send({"seq": 7, "last_sent_ms": None, "sent_once": False}) is True


def test_reliable_channel_waits_for_resend_interval_after_mark_sent() -> None:
    clock = _ManualNowMs(100)
    channel = ReliableChannel(now_ms=clock, resend_interval_ms=20)
    pending = {"seq": 7, "last_sent_ms": None, "sent_once": False}

    channel.mark_sent(pending)
    clock.value = 119
    before_interval = channel.should_send(pending)
    clock.value = 120
    after_interval = channel.should_send(pending)

    assert before_interval is False
    assert after_interval is True


def test_reliable_channel_clears_pending_when_ack_matches() -> None:
    channel = ReliableChannel(now_ms=lambda: 0, resend_interval_ms=20)
    pending = {"seq": 7, "last_sent_ms": 10, "sent_once": True}

    next_pending, matched = channel.consume_ack(pending, 7)

    assert matched is True
    assert next_pending is None


def test_reliable_channel_keeps_pending_when_ack_does_not_match() -> None:
    channel = ReliableChannel(now_ms=lambda: 0, resend_interval_ms=20)
    pending = {"reliable_seq": 9, "last_sent_ms": 10, "sent_once": True}

    next_pending, matched = channel.consume_ack(
        pending,
        7,
        seq_field="reliable_seq",
    )

    assert matched is False
    assert next_pending is pending
