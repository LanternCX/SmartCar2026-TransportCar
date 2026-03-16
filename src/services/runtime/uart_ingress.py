"""UART ingress 收包, 分行与分路服务."""


class UartIngressService:
    """拥有 UART3/UART6 的收包缓冲和入口分发逻辑."""

    _VISUAL_QUERY_PREFIX = "?frame="
    _VISUAL_PAYLOAD_KEYS = (
        "left",
        "top",
        "right",
        "bottom",
        "x",
        "y",
        "camera_id",
        "frame_id",
        "category",
        "frame_end",
    )

    def __init__(
        self,
        router,
        ensure_query_handlers,
        build_context,
        apply_command,
        command_log,
        emit_error,
        now_ms,
        vision_coordinator=None,
        get_vision_coordinator=None,
    ):
        self.router = router
        self.ensure_query_handlers = ensure_query_handlers
        self.vision_coordinator = vision_coordinator
        self.get_vision_coordinator = get_vision_coordinator
        self.build_context = build_context
        self.apply_command = apply_command
        self.command_log = command_log
        self.emit_error = emit_error
        self.now_ms = now_ms
        self._buffers = {"uart3": "", "uart6": ""}

    def _resolve_vision_coordinator(self):
        """返回当前视觉协调器, 仅在确有视觉流量时才触发 provider."""
        provider = getattr(self, "get_vision_coordinator", None)
        if callable(provider):
            return provider()
        return getattr(self, "vision_coordinator", None)

    def _is_visual_query_candidate(self, line: str) -> bool:
        """判断 query 是否明显属于视觉保留查询."""
        text = str(line).strip().lower()
        if not text.startswith(self._VISUAL_QUERY_PREFIX):
            return False
        return bool(text.split("=", 1)[1].strip())

    def _is_visual_payload_candidate(self, line: str) -> bool:
        """用轻量 key 探测视觉载荷, 避免普通串口流量提前拉起视觉链."""
        saw_visual_key = False
        for part in str(line).split(","):
            item = part.strip()
            if not item:
                continue
            if "=" not in item:
                return False
            key = item.split("=", 1)[0].strip().lower()
            if not key:
                return saw_visual_key
            if key in self._VISUAL_PAYLOAD_KEYS:
                saw_visual_key = True
        return saw_visual_key

    def _record_query_failure(self, ctx, exc: Exception) -> bool:
        """尽量用轻量状态记录 query 失败, 避免日志风暴."""
        runtime = getattr(ctx, "_runtime", None)
        if runtime is None:
            return False
        runtime.last_exception_text = str(exc)
        runtime.error_count = int(getattr(runtime, "error_count", 0) or 0) + 1
        runtime.last_error_stage = "query"
        return True

    def _build_query_error_response(self, token: str, exc: Exception) -> str:
        """构造带异常类型的最小 query 错误响应."""
        return "?%s=error:%s\r\n" % (token, exc.__class__.__name__)

    def handle_line(self, line: str, source: str) -> None:
        """处理单行串口输入, 保持视觉优先和原串口回包语义."""
        if not line:
            return

        if line.startswith("?"):
            if source == "uart6" and self._is_visual_query_candidate(line):
                coordinator = self._resolve_vision_coordinator()
                protocol = getattr(coordinator, "protocol", None)
                if (
                    protocol is not None
                    and hasattr(protocol, "is_reserved_query")
                    and protocol.is_reserved_query(line)
                ):
                    return
            token = line[1:]
            ctx = self.build_context(source)
            try:
                self.ensure_query_handlers()
                self.router.handle_query(token, ctx)
            except Exception as exc:
                if not self._record_query_failure(ctx, exc):
                    self.emit_error(str(exc))
                reply = getattr(ctx, "reply", None)
                if callable(reply):
                    try:
                        reply(self._build_query_error_response(token, exc))
                    except Exception:
                        return
                    return
                uart = getattr(ctx, "write", None)
                if callable(uart):
                    try:
                        uart(self._build_query_error_response(token, exc))
                    except Exception:
                        return
            return

        if source == "uart6" and self._is_visual_payload_candidate(line):
            coordinator = self._resolve_vision_coordinator()
            consume_uart_line = getattr(coordinator, "consume_uart_line", None)
            if callable(consume_uart_line) and consume_uart_line(
                line, source, self.now_ms()
            ):
                return

        if source == "uart3":
            self.command_log(line)
        self.apply_command(line, source=source)

    def poll_source(self, uart, source: str) -> None:
        """轮询单个串口, 拆行后交给统一入口处理."""
        buf_len = uart.any()
        if not buf_len:
            return

        try:
            raw = uart.read(buf_len)
            if raw is None:
                return
            chunk = raw.decode()
            existing = self._buffers.get(source, "")
            if existing:
                self._buffers[source] = existing + chunk
            else:
                self._buffers[source] = chunk
            while True:
                rx_buf = self._buffers.get(source, "")
                idx = rx_buf.find("\n")
                if idx == -1:
                    break
                line = rx_buf[:idx].rstrip("\r").strip()
                self._buffers[source] = rx_buf[idx + 1 :]
                self.handle_line(line, source)
        except Exception as exc:
            self.emit_error(str(exc))
