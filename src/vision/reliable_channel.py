"""视觉可靠短包共享机制.

@file src/vision/reliable_channel.py
"""

from protocol.link import should_resend


class ReliableChannel:
    """待确认可靠短包的最小共享通道."""

    def __init__(self, now_ms, resend_interval_ms: int) -> None:
        self._now_ms = now_ms
        self._resend_interval_ms = int(resend_interval_ms)

    def should_send(self, pending: dict | None) -> bool:
        """判断当前待确认短包是否到达发送时机."""

        return self.should_send_at(pending, self._now_ms())

    def should_send_at(self, pending: dict | None, now_ms: int) -> bool:
        """使用给定时刻判断当前待确认短包是否到达发送时机."""

        if pending is None:
            return False
        return should_resend(
            now_ms,
            pending.get("last_sent_ms"),
            self._resend_interval_ms,
        )

    def mark_sent(self, pending: dict) -> None:
        """记录待确认短包已经发送."""

        self.mark_sent_at(pending, self._now_ms())

    @staticmethod
    def mark_sent_at(pending: dict, now_ms: int) -> None:
        """使用给定时刻记录待确认短包已经发送."""

        pending["last_sent_ms"] = int(now_ms)
        pending["sent_once"] = True

    @staticmethod
    def ack_matches(pending: dict | None, seq: int, seq_field: str = "seq") -> bool:
        """判断 ACK 是否匹配当前待确认短包."""

        return bool(
            pending is not None
            and pending.get("sent_once")
            and int(seq) == int(pending[seq_field])
        )

    def consume_ack(
        self,
        pending: dict | None,
        seq: int,
        seq_field: str = "seq",
    ):
        """按 ACK 序号消费待确认短包."""

        if self.ack_matches(pending, seq, seq_field=seq_field):
            return None, True
        return pending, False
