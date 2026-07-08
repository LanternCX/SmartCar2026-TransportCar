"""
@file src/protocol/transport.py
@brief 统一通信调度服务
"""

import time

from config import comm as comm_params
from protocol.frame import (
    FRAME_SIZE,
    MODE_ACK,
    MODE_TCP,
    MODE_UDP,
    decode_frame_fields,
    encode_frame,
)
from protocol.topic import (
    ROLE_ASSISTANT,
    ROLE_MASTER,
    UART6,
    UART8,
    can_role_read,
    can_role_write,
    get_topic_entry,
    get_topic_body_size,
    validate_body_bytes,
    validate_mode_for_topic,
    validate_port_for_topic,
)

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


RX_READ_LIMIT = comm_params.TRANSPORT_RX_READ_LIMIT
UDP_SEND_INTERVAL_MS = comm_params.UDP_SEND_INTERVAL_MS
TCP_SEND_INTERVAL_MS = comm_params.TCP_SEND_INTERVAL_MS
SEQ_RING_SIZE = comm_params.SEQ_RING_SIZE

WRITE_ACCEPTED = "accepted"
WRITE_OVERWRITTEN = "overwritten"
WRITE_DROPPED_PRIORITY = "dropped_priority"
WRITE_DROPPED_BUSY = "dropped_busy"
WRITE_INVALID = "invalid"

READ_OK = "ok"
READ_EMPTY = "empty"
READ_INVALID = "invalid"

DELIVERY_IDLE = "idle"
DELIVERY_PENDING = "pending"
DELIVERY_DELIVERED = "delivered"
DELIVERY_DROPPED = "dropped"
DELIVERY_INVALID = "invalid"

_DELIVERY_IDLE_CODE = const(0)
_DELIVERY_PENDING_CODE = const(1)
_DELIVERY_DELIVERED_CODE = const(2)
_DELIVERY_DROPPED_CODE = const(3)


def _delivery_label(code):
    code = int(code)
    if code == _DELIVERY_PENDING_CODE:
        return DELIVERY_PENDING
    if code == _DELIVERY_DELIVERED_CODE:
        return DELIVERY_DELIVERED
    if code == _DELIVERY_DROPPED_CODE:
        return DELIVERY_DROPPED
    return DELIVERY_IDLE


def _default_now_ms():
    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def _copy_body(body):
    if isinstance(body, bytes):
        return body
    if isinstance(body, bytearray):
        return bytes(body)
    if isinstance(body, memoryview):
        return body.tobytes()
    raise TypeError("body must be bytes-like")


class _UdpHandle:
    def __init__(self, service, port):
        self._service = service
        self._port = port

    def write(self, topic, body):
        return self._service._udp_write(self._port, topic, body)

    def read(self, topic, out_body):
        return self._service._udp_read(self._port, topic, out_body)


class _TcpHandle:
    def __init__(self, service, port):
        self._service = service
        self._port = port

    def write(self, topic, body):
        return self._service._tcp_write(self._port, topic, body)

    def read(self, topic, out_body):
        return self._service._tcp_read(self._port, topic, out_body)

    def delivery(self, topic):
        return self._service._tcp_delivery(self._port, topic)


_ST_NAME = const(0)
_ST_UART = const(1)
_ST_RX_BUFFER = const(2)
_ST_UDP_RX = const(3)
_ST_UDP_RX_VERSIONS = const(4)
_ST_UDP_TX = const(5)
_ST_TCP_RX_TOPIC = const(6)
_ST_TCP_RX_SEQ = const(7)
_ST_TCP_RX_BODY = const(8)
_ST_TCP_TX_TOPIC = const(9)
_ST_TCP_TX_BODY = const(10)
_ST_TCP_TX_SEQ = const(11)
_ST_TCP_TX_LAST_SENT_MS = const(12)
_ST_TCP_TX_INTENT_TOPIC = const(13)
_ST_TCP_TX_INTENT_BODY = const(14)
_ST_NEXT_SEQ = const(15)
_ST_LAST_DELIVERY_TOPIC = const(16)
_ST_LAST_DELIVERY_CODE = const(17)
_ST_LAST_RX_TOPIC = const(18)
_ST_LAST_RX_SEQ = const(19)
_ST_UDP_LAST_SENT_MS = const(20)
_ST_RX_READS = const(21)
_ST_DROPPED_TRUNCATED_FRAMES = const(22)
_ST_DROPPED_INVALID_FRAMES = const(23)
_ST_TCP_RETRIES = const(24)
_ST_ACK_RX = const(25)
_ST_ACK_TX = const(26)
_ST_UDP_OVERWRITES = const(27)
_ST_PRIORITY_DROPS = const(28)
_ST_BUSY_DROPS = const(29)
_ST_ACK_OVERWRITES = const(30)
_ST_TX_FRAMES = const(31)


def _new_port_state(port, uart):
    if uart is None:
        uart = _try_create_uart(port)
    return [
        port,
        uart,
        b"",
        {},
        {},
        {},
        -1,
        0,
        None,
        -1,
        None,
        0,
        None,
        -1,
        None,
        0,
        -1,
        _DELIVERY_IDLE_CODE,
        -1,
        -1,
        None,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]


class TransportService:
    """统一通信服务."""

    def __init__(self, role, uart6=None, uart8=None, now_ms=None):
        self.role = role
        self._now_ms = now_ms or _default_now_ms
        self._rr_next_port = UART6
        self._udp_candidate = None
        self._udp_candidate_port = None
        self._udp_candidate_topic = 0
        self._ack_candidate = None
        self._ack_candidate_port = None
        self._ack_candidate_topic = 0
        self._ack_candidate_seq = 0
        self._uart6_state = _new_port_state(UART6, uart6)
        self._uart8_state = _new_port_state(UART8, uart8)
        self._udp6 = _UdpHandle(self, UART6)
        self._udp8 = _UdpHandle(self, UART8)
        self._tcp6 = _TcpHandle(self, UART6)
        self._tcp8 = _TcpHandle(self, UART8)

    def _find_port_state(self, port):
        if port == UART6:
            return self._uart6_state
        if port == UART8:
            return self._uart8_state
        return None

    def _port_state(self, port):
        if port == UART6:
            return self._uart6_state
        return self._uart8_state

    def udp(self, port):
        if port == UART6:
            return self._udp6
        if port == UART8:
            return self._udp8
        return _UdpHandle(self, port)

    def tcp(self, port):
        if port == UART6:
            return self._tcp6
        if port == UART8:
            return self._tcp8
        return _TcpHandle(self, port)

    def diagnostics(self, port):
        state = self._find_port_state(port)
        if state is None:
            return {}
        return {
            "rx_reads": state[_ST_RX_READS],
            "dropped_truncated_frames": state[_ST_DROPPED_TRUNCATED_FRAMES],
            "dropped_invalid_frames": state[_ST_DROPPED_INVALID_FRAMES],
            "tcp_retries": state[_ST_TCP_RETRIES],
            "ack_rx": state[_ST_ACK_RX],
            "ack_tx": state[_ST_ACK_TX],
            "udp_overwrites": state[_ST_UDP_OVERWRITES],
            "priority_drops": state[_ST_PRIORITY_DROPS],
            "busy_drops": state[_ST_BUSY_DROPS],
            "ack_overwrites": state[_ST_ACK_OVERWRITES],
            "tx_frames": state[_ST_TX_FRAMES],
            "tcp_tx_busy": state[_ST_TCP_TX_BODY] is not None
            or state[_ST_TCP_TX_INTENT_BODY] is not None,
            "tcp_rx_busy": state[_ST_TCP_RX_BODY] is not None,
            "ack_pending": self._ack_candidate is not None
            and self._ack_candidate_port == port,
        }

    def poll_rx(self):
        """按固定顺序轮询两个端口的接收侧.

        @details 每个调度周期只主动请求每个端口一轮读取, 其余由固定槽和版本号消化
        """
        self._poll_port_rx(UART6)
        self._poll_port_rx(UART8)

    def poll_tx(self):
        """按 ACK -> TCP -> UDP 的优先级放行本周期唯一一帧."""
        self._materialize_tcp_intents()
        if self._send_ack_if_pending():
            return True
        if self._send_tcp_if_due():
            return True
        if self._send_udp_if_due():
            return True
        return False

    def clear_udp(self, port, topic):
        state = self._find_port_state(port)
        if state is None:
            return False
        if topic in state[_ST_UDP_RX]:
            del state[_ST_UDP_RX][topic]
            state[_ST_UDP_RX_VERSIONS].pop(int(topic), None)
            return True
        return False

    def get_udp_version(self, port, topic):
        state = self._find_port_state(port)
        if state is None:
            return 0
        return int(state[_ST_UDP_RX_VERSIONS].get(int(topic), 0))

    def _validate_topic(self, port, topic, mode, operation):
        entry = get_topic_entry(topic)
        if entry is None:
            return None
        if not validate_mode_for_topic(topic, mode):
            return None
        if not validate_port_for_topic(topic, port):
            return None
        if operation == "write" and not can_role_write(topic, self.role):
            return None
        if operation == "read" and not can_role_read(topic, self.role):
            return None
        return entry

    def _udp_write(self, port, topic, body):
        entry = self._validate_topic(port, topic, MODE_UDP, "write")
        if entry is None or not validate_body_bytes(topic, body):
            return WRITE_INVALID
        if self._ack_candidate is not None or self._has_pending_tcp_intent():
            self._port_state(port)[_ST_PRIORITY_DROPS] += 1
            return WRITE_DROPPED_PRIORITY
        state = self._port_state(port)
        stored = _copy_body(body)
        overwritten = topic in state[_ST_UDP_TX]
        state[_ST_UDP_TX][topic] = stored
        self._udp_candidate = True
        self._udp_candidate_port = port
        self._udp_candidate_topic = int(topic)
        if overwritten:
            state[_ST_UDP_OVERWRITES] += 1
            return WRITE_OVERWRITTEN
        return WRITE_ACCEPTED

    def _udp_read(self, port, topic, out_body):
        entry = self._validate_topic(port, topic, MODE_UDP, "read")
        if entry is None:
            return READ_INVALID
        body = self._port_state(port)[_ST_UDP_RX].get(int(topic))
        if body is None:
            return READ_EMPTY
        if not _write_out_body(out_body, body):
            return READ_INVALID
        return READ_OK

    def _tcp_write(self, port, topic, body):
        entry = self._validate_topic(port, topic, MODE_TCP, "write")
        if entry is None or not validate_body_bytes(topic, body):
            return WRITE_INVALID
        if self._ack_candidate is not None:
            state = self._port_state(port)
            state[_ST_PRIORITY_DROPS] += 1
            state[_ST_LAST_DELIVERY_TOPIC] = int(topic)
            state[_ST_LAST_DELIVERY_CODE] = _DELIVERY_DROPPED_CODE
            return WRITE_DROPPED_PRIORITY
        state = self._port_state(port)
        if state[_ST_TCP_TX_BODY] is not None:
            state[_ST_BUSY_DROPS] += 1
            state[_ST_LAST_DELIVERY_TOPIC] = int(topic)
            state[_ST_LAST_DELIVERY_CODE] = _DELIVERY_DROPPED_CODE
            return WRITE_DROPPED_BUSY
        stored = _copy_body(body)
        if state[_ST_TCP_TX_INTENT_BODY] is not None:
            state[_ST_LAST_DELIVERY_TOPIC] = int(topic)
            state[_ST_LAST_DELIVERY_CODE] = _DELIVERY_PENDING_CODE
            state[_ST_TCP_TX_INTENT_TOPIC] = int(topic)
            state[_ST_TCP_TX_INTENT_BODY] = stored
            return WRITE_OVERWRITTEN
        state[_ST_TCP_TX_INTENT_TOPIC] = int(topic)
        state[_ST_TCP_TX_INTENT_BODY] = stored
        state[_ST_LAST_DELIVERY_TOPIC] = int(topic)
        state[_ST_LAST_DELIVERY_CODE] = _DELIVERY_PENDING_CODE
        return WRITE_ACCEPTED

    def _tcp_read(self, port, topic, out_body):
        entry = self._validate_topic(port, topic, MODE_TCP, "read")
        if entry is None:
            return READ_INVALID
        state = self._port_state(port)
        if state[_ST_TCP_RX_BODY] is None or int(state[_ST_TCP_RX_TOPIC]) != int(topic):
            return READ_EMPTY
        if not _write_out_body(out_body, state[_ST_TCP_RX_BODY]):
            return READ_INVALID
        state[_ST_TCP_RX_BODY] = None
        state[_ST_TCP_RX_TOPIC] = -1
        return READ_OK

    def _tcp_delivery(self, port, topic):
        entry = self._validate_topic(port, topic, MODE_TCP, "write")
        if entry is None:
            return DELIVERY_INVALID
        state = self._port_state(port)
        if state[_ST_TCP_TX_BODY] is not None and int(state[_ST_TCP_TX_TOPIC]) == int(topic):
            return DELIVERY_PENDING
        if (
            state[_ST_TCP_TX_INTENT_BODY] is not None
            and int(state[_ST_TCP_TX_INTENT_TOPIC]) == int(topic)
        ):
            return DELIVERY_PENDING
        if state[_ST_LAST_DELIVERY_TOPIC] == int(topic):
            return _delivery_label(state[_ST_LAST_DELIVERY_CODE])
        return DELIVERY_IDLE

    def _materialize_tcp_intents(self):
        """把本周期可靠写入意图转成固定发送槽.

        @details 只有发送槽空闲时才会分配可靠序号, 避免同链路同时出现多份待确认 TCP
        """
        for port in (UART6, UART8):
            state = self._port_state(port)
            if state[_ST_TCP_TX_BODY] is not None:
                continue
            if state[_ST_TCP_TX_INTENT_BODY] is None:
                continue
            seq = int(state[_ST_NEXT_SEQ])
            state[_ST_NEXT_SEQ] = (seq + 1) % SEQ_RING_SIZE
            state[_ST_TCP_TX_TOPIC] = int(state[_ST_TCP_TX_INTENT_TOPIC])
            state[_ST_TCP_TX_BODY] = state[_ST_TCP_TX_INTENT_BODY]
            state[_ST_TCP_TX_SEQ] = seq
            state[_ST_TCP_TX_LAST_SENT_MS] = None
            state[_ST_TCP_TX_INTENT_TOPIC] = -1
            state[_ST_TCP_TX_INTENT_BODY] = None

    def _send_ack_if_pending(self):
        """发送当前待确认对象的 ACK."""
        if self._ack_candidate is None:
            return False
        port = self._ack_candidate_port
        topic = self._ack_candidate_topic
        seq = self._ack_candidate_seq
        state = self._port_state(port)
        if not _write_uart_frame(
            state[_ST_UART], encode_frame(MODE_ACK, topic, seq, b"")
        ):
            return False
        state[_ST_ACK_TX] += 1
        state[_ST_TX_FRAMES] += 1
        self._ack_candidate = None
        return True

    def _send_tcp_if_due(self):
        """发送或重发到达节奏点的可靠帧."""
        now_ms = self._now_ms()
        uart6_due = self._is_tcp_due(self._uart6_state, now_ms)
        uart8_due = self._is_tcp_due(self._uart8_state, now_ms)
        if not uart6_due and not uart8_due:
            return False
        if uart6_due and uart8_due:
            port = self._rr_next_port
        elif uart6_due:
            port = UART6
        else:
            port = UART8
        self._rr_next_port = UART8 if port == UART6 else UART6
        state = self._port_state(port)
        frame = encode_frame(
            MODE_TCP,
            state[_ST_TCP_TX_TOPIC],
            state[_ST_TCP_TX_SEQ],
            state[_ST_TCP_TX_BODY],
        )
        if not _write_uart_frame(state[_ST_UART], frame):
            return False
        if state[_ST_TCP_TX_LAST_SENT_MS] is not None:
            state[_ST_TCP_RETRIES] += 1
        state[_ST_TCP_TX_LAST_SENT_MS] = now_ms
        state[_ST_TX_FRAMES] += 1
        return True

    def _is_tcp_due(self, state, now_ms):
        if state[_ST_TCP_TX_BODY] is None:
            return False
        last_sent_ms = state[_ST_TCP_TX_LAST_SENT_MS]
        return last_sent_ms is None or now_ms - int(last_sent_ms) >= int(TCP_SEND_INTERVAL_MS)

    def _send_udp_if_due(self):
        """发送最新值 UDP 候选.

        @details UDP 不排队, 这里只发送当前候选槽里的最新 body
        """
        if self._udp_candidate is None:
            return False
        port = self._udp_candidate_port
        topic = self._udp_candidate_topic
        state = self._port_state(port)
        body = state[_ST_UDP_TX].get(int(topic))
        if body is None:
            return False
        now_ms = self._now_ms()
        last_sent_ms = state[_ST_UDP_LAST_SENT_MS]
        if last_sent_ms is not None and now_ms - int(last_sent_ms) < int(UDP_SEND_INTERVAL_MS):
            return False
        frame = encode_frame(MODE_UDP, topic, 0, body)
        if not _write_uart_frame(state[_ST_UART], frame):
            return False
        state[_ST_UDP_LAST_SENT_MS] = now_ms
        state[_ST_TX_FRAMES] += 1
        return True

    def _poll_port_rx(self, port):
        """对单个端口执行一轮受限读取."""
        state = self._port_state(port)
        uart = state[_ST_UART]
        if uart is None or getattr(uart, "any", None) is None:
            return
        state[_ST_RX_READS] += 1
        try:
            pending = int(uart.any())
        except Exception:
            return
        if pending <= 0:
            return
        read_size = pending if pending <= int(RX_READ_LIMIT) else int(RX_READ_LIMIT)
        try:
            chunk = uart.read(read_size)
        except Exception:
            return
        if chunk is None:
            return
        if pending > int(RX_READ_LIMIT):
            self._handle_rx_chunk(port, bytes(chunk))
            state[_ST_RX_BUFFER] = b""
            self._drain_port_overflow(uart)
            return
        self._handle_rx_chunk(port, bytes(chunk))

    def _drain_port_overflow(self, uart):
        while True:
            try:
                pending = int(uart.any())
            except Exception:
                return
            if pending <= 0:
                return
            read_size = pending if pending <= int(RX_READ_LIMIT) else int(RX_READ_LIMIT)
            try:
                uart.read(read_size)
            except Exception:
                return

    def _handle_rx_chunk(self, port, chunk):
        """把本轮读取到的 bytes 扫描成固定帧并分发."""
        state = self._port_state(port)
        if len(chunk) < 1:
            return
        chunk = state[_ST_RX_BUFFER] + chunk
        frame_size = FRAME_SIZE
        offset = 0
        while offset + frame_size <= len(chunk):
            fields = decode_frame_fields(chunk, offset)
            if fields is None:
                offset += 1
                continue
            mode, topic, seq = fields
            if not self._can_dispatch_frame_fields(port, mode, topic):
                offset += 1
                continue
            self._dispatch_frame_fields(port, mode, topic, seq, chunk, offset)
            offset += frame_size
        state[_ST_RX_BUFFER] = chunk[offset:]

    def _can_dispatch_frame_fields(self, port, mode, topic):
        entry = get_topic_entry(topic)
        if entry is None:
            return False
        if not validate_port_for_topic(topic, port):
            return False
        if mode == MODE_ACK:
            return True
        if not validate_mode_for_topic(topic, mode):
            return False
        if not can_role_read(topic, self.role):
            return False
        return True

    def _dispatch_frame_fields(self, port, mode, topic, seq, frame_bytes, frame_offset):
        """把单个固定帧路由到 ACK、TCP 或 UDP 槽."""
        entry = get_topic_entry(topic)
        state = self._port_state(port)
        if entry is None:
            state[_ST_DROPPED_INVALID_FRAMES] += 1
            return
        if not validate_port_for_topic(topic, port):
            state[_ST_DROPPED_INVALID_FRAMES] += 1
            return
        if mode == MODE_ACK:
            if (
                state[_ST_TCP_TX_BODY] is not None
                and int(state[_ST_TCP_TX_TOPIC]) == topic
                and int(state[_ST_TCP_TX_SEQ]) == seq
            ):
                state[_ST_TCP_TX_BODY] = None
                state[_ST_TCP_TX_TOPIC] = -1
                state[_ST_LAST_DELIVERY_TOPIC] = topic
                state[_ST_LAST_DELIVERY_CODE] = _DELIVERY_DELIVERED_CODE
                state[_ST_ACK_RX] += 1
            return
        if not validate_mode_for_topic(topic, mode):
            state[_ST_DROPPED_INVALID_FRAMES] += 1
            return
        if mode == MODE_UDP:
            if not can_role_read(topic, self.role):
                state[_ST_DROPPED_INVALID_FRAMES] += 1
                return
            body_size = get_topic_body_size(topic)
            body_start = int(frame_offset) + 4
            state[_ST_UDP_RX][topic] = frame_bytes[body_start : body_start + body_size]
            state[_ST_UDP_RX_VERSIONS][topic] = (
                int(state[_ST_UDP_RX_VERSIONS].get(topic, 0)) + 1
            )
            return
        if mode == MODE_TCP:
            if not can_role_read(topic, self.role):
                state[_ST_DROPPED_INVALID_FRAMES] += 1
                return
            if state[_ST_LAST_RX_TOPIC] == topic and state[_ST_LAST_RX_SEQ] == seq:
                self._schedule_ack(port, topic, seq)
                return
            if state[_ST_TCP_RX_BODY] is not None:
                return
            body_size = get_topic_body_size(topic)
            body_start = int(frame_offset) + 4
            state[_ST_TCP_RX_TOPIC] = topic
            state[_ST_TCP_RX_SEQ] = seq
            state[_ST_TCP_RX_BODY] = frame_bytes[body_start : body_start + body_size]
            state[_ST_LAST_RX_TOPIC] = topic
            state[_ST_LAST_RX_SEQ] = seq
            self._schedule_ack(port, topic, seq)

    def _schedule_ack(self, port, topic, seq):
        """登记待发送 ACK.

        @details 不同确认对象同时出现时, 只保留尚未写出的最新 ACK 候选
        """
        topic = int(topic)
        seq = int(seq)
        if self._ack_candidate is None:
            self._ack_candidate = True
            self._ack_candidate_port = port
            self._ack_candidate_topic = topic
            self._ack_candidate_seq = seq
            return
        if (
            self._ack_candidate_port == port
            and self._ack_candidate_topic == topic
            and self._ack_candidate_seq == seq
        ):
            return
        self._port_state(port)[_ST_ACK_OVERWRITES] += 1
        self._ack_candidate = True
        self._ack_candidate_port = port
        self._ack_candidate_topic = topic
        self._ack_candidate_seq = seq

    def _has_pending_tcp_intent(self):
        for port in (UART6, UART8):
            state = self._port_state(port)
            if state[_ST_TCP_TX_INTENT_BODY] is not None:
                return True
        return False


def _write_out_body(out_body, body):
    if isinstance(out_body, memoryview):
        if len(out_body) < len(body):
            return False
        out_body[: len(body)] = body
        return True
    if isinstance(out_body, bytearray):
        if len(out_body) < len(body):
            return False
        out_body[: len(body)] = body
        return True
    return False


def _write_uart_frame(uart, frame):
    if uart is None or getattr(uart, "write", None) is None:
        return False
    try:
        written = uart.write(frame)
    except Exception:
        return False
    if written is None:
        return False
    return int(written) == len(frame)


def _try_create_uart(port):
    try:
        from hardware import uart_bus
    except Exception:
        return None
    if port == UART6:
        factory = getattr(uart_bus, "create_uart6", None)
    else:
        factory = getattr(uart_bus, "create_uart8", None)
    if factory is None:
        return None
    try:
        return factory()
    except Exception:
        return None


def create_transport(role, uart6=None, uart8=None, now_ms=None):
    """创建通信服务."""

    if role != ROLE_MASTER and role != ROLE_ASSISTANT:
        raise ValueError("unsupported role")
    return TransportService(role, uart6=uart6, uart8=uart8, now_ms=now_ms)
