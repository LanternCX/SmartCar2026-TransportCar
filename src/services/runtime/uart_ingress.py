"""UART ingress 收包, 分行与分路服务."""


class UartIngressService:
    """拥有 UART3/UART6 的收包缓冲和入口分发逻辑."""

    def __init__(
        self,
        router,
        vision_coordinator,
        build_context,
        apply_command,
        command_log,
        emit_error,
        now_ms,
    ):
        self.router = router
        self.vision_coordinator = vision_coordinator
        self.build_context = build_context
        self.apply_command = apply_command
        self.command_log = command_log
        self.emit_error = emit_error
        self.now_ms = now_ms
        self._buffers = {"uart3": "", "uart6": ""}

    def handle_line(self, line: str, source: str) -> None:
        """处理单行串口输入, 保持视觉优先和原串口回包语义."""
        if not line:
            return

        if line.startswith("?"):
            self.router.handle_query(line[1:], self.build_context(source))
            return

        if source == "uart6" and self.vision_coordinator.consume_uart_line(
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
            self._buffers[source] = self._buffers.get(source, "") + raw.decode()
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
