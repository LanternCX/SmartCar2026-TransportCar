"""
@file src/protocol/transport.py
@brief 统一通信调度服务
"""

from config import comm as comm_params
from protocol.frame import FRAME_SIZE, MODE_ACK, MODE_TCP, MODE_UDP, decode_frame, encode_frame
from protocol.topic import (
    ROLE_ASSISTANT,
    ROLE_MASTER,
    UART6,
    UART8,
    can_role_read,
    can_role_write,
    get_topic_entry,
    validate_body_bytes,
    validate_mode_for_topic,
    validate_port_for_topic,
)


RX_READ_LIMIT = getattr(comm_params, "TRANSPORT_RX_READ_LIMIT", 32)
UDP_SEND_INTERVAL_MS = getattr(comm_params, "UDP_SEND_INTERVAL_MS")
TCP_SEND_INTERVAL_MS = getattr(comm_params, "TCP_SEND_INTERVAL_MS")
SEQ_RING_SIZE = getattr(comm_params, "SEQ_RING_SIZE")

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


def _default_now_ms():
    import time

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


class TransportService:
    """统一通信服务."""

    def __init__(self, role, uart6=None, uart8=None, now_ms=None):
        self.role = role
        self._now_ms = now_ms or _default_now_ms
        self._rr_next_port = UART6
        self._udp_candidate = None
        self._ack_candidate = None
        self._ports = {
            UART6: self._build_port_state(UART6, uart6),
            UART8: self._build_port_state(UART8, uart8),
        }

    def _build_port_state(self, port, uart):
        if uart is None:
            uart = _try_create_uart(port)
        return {
            "name": port,
            "uart": uart,
            "rx_buffer": b"",
            "udp_rx": {},
            "udp_rx_versions": {},
            "udp_tx": {},
            "tcp_rx_slot": None,
            "tcp_tx_slot": None,
            "tcp_tx_intent": None,
            "next_seq": 0,
            "last_delivery": {},
            "last_rx_token": None,
            "udp_last_sent_ms": None,
            "stats": {
                "rx_reads": 0,
                "dropped_truncated_frames": 0,
                "dropped_invalid_frames": 0,
                "tcp_retries": 0,
                "ack_rx": 0,
                "ack_tx": 0,
                "udp_overwrites": 0,
                "priority_drops": 0,
                "busy_drops": 0,
                "ack_overwrites": 0,
                "tx_frames": 0,
            },
        }

    def udp(self, port):
        return _UdpHandle(self, port)

    def tcp(self, port):
        return _TcpHandle(self, port)

    def diagnostics(self, port):
        state = self._ports.get(port)
        if state is None:
            return {}
        snapshot = dict(state["stats"])
        snapshot["tcp_tx_busy"] = state["tcp_tx_slot"] is not None or state["tcp_tx_intent"] is not None
        snapshot["tcp_rx_busy"] = state["tcp_rx_slot"] is not None
        snapshot["ack_pending"] = self._ack_candidate is not None and self._ack_candidate["port"] == port
        return snapshot

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
        state = self._ports.get(port)
        if state is None:
            return False
        if topic in state["udp_rx"]:
            del state["udp_rx"][topic]
            state["udp_rx_versions"].pop(int(topic), None)
            return True
        return False

    def get_udp_version(self, port, topic):
        state = self._ports.get(port)
        if state is None:
            return 0
        return int(state["udp_rx_versions"].get(int(topic), 0))

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
            self._ports[port]["stats"]["priority_drops"] += 1
            return WRITE_DROPPED_PRIORITY
        state = self._ports[port]
        stored = _copy_body(body)
        overwritten = topic in state["udp_tx"]
        state["udp_tx"][topic] = stored
        self._udp_candidate = {"port": port, "topic": topic}
        if overwritten:
            state["stats"]["udp_overwrites"] += 1
            return WRITE_OVERWRITTEN
        return WRITE_ACCEPTED

    def _udp_read(self, port, topic, out_body):
        entry = self._validate_topic(port, topic, MODE_UDP, "read")
        if entry is None:
            return READ_INVALID
        body = self._ports[port]["udp_rx"].get(int(topic))
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
            self._ports[port]["stats"]["priority_drops"] += 1
            self._ports[port]["last_delivery"][int(topic)] = DELIVERY_DROPPED
            return WRITE_DROPPED_PRIORITY
        state = self._ports[port]
        if state["tcp_tx_slot"] is not None:
            state["stats"]["busy_drops"] += 1
            state["last_delivery"][int(topic)] = DELIVERY_DROPPED
            return WRITE_DROPPED_BUSY
        stored = _copy_body(body)
        if state["tcp_tx_intent"] is not None:
            state["last_delivery"][int(topic)] = DELIVERY_PENDING
            state["tcp_tx_intent"] = {"topic": int(topic), "body": stored}
            return WRITE_OVERWRITTEN
        state["tcp_tx_intent"] = {"topic": int(topic), "body": stored}
        state["last_delivery"][int(topic)] = DELIVERY_PENDING
        return WRITE_ACCEPTED

    def _tcp_read(self, port, topic, out_body):
        entry = self._validate_topic(port, topic, MODE_TCP, "read")
        if entry is None:
            return READ_INVALID
        slot = self._ports[port]["tcp_rx_slot"]
        if slot is None or int(slot["topic"]) != int(topic):
            return READ_EMPTY
        if not _write_out_body(out_body, slot["body"]):
            return READ_INVALID
        self._ports[port]["tcp_rx_slot"] = None
        return READ_OK

    def _tcp_delivery(self, port, topic):
        entry = self._validate_topic(port, topic, MODE_TCP, "write")
        if entry is None:
            return DELIVERY_INVALID
        state = self._ports[port]
        if state["tcp_tx_slot"] is not None and int(state["tcp_tx_slot"]["topic"]) == int(topic):
            return DELIVERY_PENDING
        if state["tcp_tx_intent"] is not None and int(state["tcp_tx_intent"]["topic"]) == int(topic):
            return DELIVERY_PENDING
        return state["last_delivery"].get(int(topic), DELIVERY_IDLE)

    def _materialize_tcp_intents(self):
        """把本周期可靠写入意图转成固定发送槽.

        @details 只有发送槽空闲时才会分配可靠序号, 避免同链路同时出现多份待确认 TCP
        """
        for port in (UART6, UART8):
            state = self._ports[port]
            if state["tcp_tx_slot"] is not None:
                continue
            intent = state["tcp_tx_intent"]
            if intent is None:
                continue
            seq = int(state["next_seq"])
            state["next_seq"] = (seq + 1) % SEQ_RING_SIZE
            state["tcp_tx_slot"] = {
                "topic": int(intent["topic"]),
                "body": intent["body"],
                "seq": seq,
                "last_sent_ms": None,
            }
            state["tcp_tx_intent"] = None

    def _send_ack_if_pending(self):
        """发送当前待确认对象的 ACK."""
        candidate = self._ack_candidate
        if candidate is None:
            return False
        state = self._ports[candidate["port"]]
        if not _write_uart_frame(
            state["uart"], encode_frame(MODE_ACK, candidate["topic"], candidate["seq"], b"")
        ):
            return False
        state["stats"]["ack_tx"] += 1
        state["stats"]["tx_frames"] += 1
        self._ack_candidate = None
        return True

    def _send_tcp_if_due(self):
        """发送或重发到达节奏点的可靠帧."""
        due_ports = []
        now_ms = self._now_ms()
        for port in (UART6, UART8):
            slot = self._ports[port]["tcp_tx_slot"]
            if slot is None:
                continue
            last_sent_ms = slot["last_sent_ms"]
            if last_sent_ms is None or now_ms - int(last_sent_ms) >= int(TCP_SEND_INTERVAL_MS):
                due_ports.append(port)
        if not due_ports:
            return False
        port = _choose_round_robin(due_ports, self._rr_next_port)
        self._rr_next_port = UART8 if port == UART6 else UART6
        state = self._ports[port]
        slot = state["tcp_tx_slot"]
        frame = encode_frame(MODE_TCP, slot["topic"], slot["seq"], slot["body"])
        if not _write_uart_frame(state["uart"], frame):
            return False
        if slot["last_sent_ms"] is not None:
            state["stats"]["tcp_retries"] += 1
        slot["last_sent_ms"] = now_ms
        state["stats"]["tx_frames"] += 1
        return True

    def _send_udp_if_due(self):
        """发送最新值 UDP 候选.

        @details UDP 不排队, 这里只发送当前候选槽里的最新 body
        """
        candidate = self._udp_candidate
        if candidate is None:
            return False
        state = self._ports[candidate["port"]]
        body = state["udp_tx"].get(int(candidate["topic"]))
        if body is None:
            return False
        now_ms = self._now_ms()
        last_sent_ms = state["udp_last_sent_ms"]
        if last_sent_ms is not None and now_ms - int(last_sent_ms) < int(UDP_SEND_INTERVAL_MS):
            return False
        frame = encode_frame(MODE_UDP, candidate["topic"], 0, body)
        if not _write_uart_frame(state["uart"], frame):
            return False
        state["udp_last_sent_ms"] = now_ms
        state["stats"]["tx_frames"] += 1
        return True

    def _poll_port_rx(self, port):
        """对单个端口执行一轮受限读取."""
        state = self._ports[port]
        uart = state["uart"]
        if uart is None or getattr(uart, "any", None) is None:
            return
        state["stats"]["rx_reads"] += 1
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
            self._ports[port]["rx_buffer"] = b""
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
        state = self._ports[port]
        if len(chunk) < 1:
            return
        chunk = state["rx_buffer"] + chunk
        frame_size = FRAME_SIZE
        offset = 0
        while offset + frame_size <= len(chunk):
            frame = decode_frame(chunk[offset : offset + frame_size])
            if frame is None or not self._can_dispatch_frame(port, frame):
                offset += 1
                continue
            self._dispatch_frame(port, frame)
            offset += frame_size
        state["rx_buffer"] = chunk[offset:]

    def _can_dispatch_frame(self, port, frame):
        topic = int(frame["topic"])
        mode = int(frame["mode"])
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

    def _dispatch_frame(self, port, frame):
        """把单个固定帧路由到 ACK、TCP 或 UDP 槽."""
        topic = int(frame["topic"])
        mode = int(frame["mode"])
        seq = int(frame["seq"])
        entry = get_topic_entry(topic)
        state = self._ports[port]
        if entry is None:
            state["stats"]["dropped_invalid_frames"] += 1
            return
        if not validate_port_for_topic(topic, port):
            state["stats"]["dropped_invalid_frames"] += 1
            return
        if mode == MODE_ACK:
            slot = state["tcp_tx_slot"]
            if slot is not None and int(slot["topic"]) == topic and int(slot["seq"]) == seq:
                state["tcp_tx_slot"] = None
                state["last_delivery"][topic] = DELIVERY_DELIVERED
                state["stats"]["ack_rx"] += 1
            return
        if not validate_mode_for_topic(topic, mode):
            state["stats"]["dropped_invalid_frames"] += 1
            return
        if mode == MODE_UDP:
            if not can_role_read(topic, self.role):
                state["stats"]["dropped_invalid_frames"] += 1
                return
            body_size = int(entry["body_size"])
            state["udp_rx"][topic] = frame["body"][:body_size]
            state["udp_rx_versions"][topic] = int(state["udp_rx_versions"].get(topic, 0)) + 1
            return
        if mode == MODE_TCP:
            if not can_role_read(topic, self.role):
                state["stats"]["dropped_invalid_frames"] += 1
                return
            token = (topic, seq)
            if state["last_rx_token"] == token:
                self._schedule_ack(port, topic, seq)
                return
            if state["tcp_rx_slot"] is not None:
                return
            body_size = int(entry["body_size"])
            state["tcp_rx_slot"] = {
                "topic": topic,
                "seq": seq,
                "body": frame["body"][:body_size],
            }
            state["last_rx_token"] = token
            self._schedule_ack(port, topic, seq)

    def _schedule_ack(self, port, topic, seq):
        """登记待发送 ACK.

        @details 不同确认对象同时出现时, 只保留尚未写出的最新 ACK 候选
        """
        candidate = {"port": port, "topic": int(topic), "seq": int(seq)}
        if self._ack_candidate is None:
            self._ack_candidate = candidate
            return
        if (
            self._ack_candidate["port"] == candidate["port"]
            and self._ack_candidate["topic"] == candidate["topic"]
            and self._ack_candidate["seq"] == candidate["seq"]
        ):
            return
        self._ports[port]["stats"]["ack_overwrites"] += 1
        self._ack_candidate = candidate

    def _has_pending_tcp_intent(self):
        for port in (UART6, UART8):
            state = self._ports[port]
            if state["tcp_tx_intent"] is not None:
                return True
        return False


def _choose_round_robin(ports, next_port):
    if len(ports) == 1:
        return ports[0]
    if next_port in ports:
        return next_port
    return ports[0]


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
