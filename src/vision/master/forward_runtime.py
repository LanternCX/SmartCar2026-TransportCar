"""主车角色运行时主体

@file src/vision/master/forward_runtime.py
"""

from vision.serial_protocol import format_velocity_packet, parse_short_packet


class MasterForwardRuntime:
    """基于共享底盘装配主车角色运行时外观

    @brief 在共享底盘外层接管 UART3, 并把速度短包转发到 UART8
    """

    def __init__(self) -> None:
        from core.runtime import TransportCar

        car = TransportCar()
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._rx_buf3 = ""
        self._rx_buf8 = ""
        self._last_error_text = "none"
        self._sync_seq = 0
        self._pending_sync = None
        self.last_report = None

        if getattr(car, "_process_uart", None) is not None:
            car._process_uart = self._noop_transport_uart

    def mark_tick(self, tick=None) -> None:
        """转发 ticker 中断标记

        @param tick 节拍值
        """

        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        """转发 ticker 对象

        @param ticker_obj ticker 对象
        """

        self._transport_car.set_ticker(ticker_obj)

    def step(self) -> bool:
        """执行一拍主车角色运行时

        @return 是否继续运行
        """

        try:
            self._run_role_cycle()
        except Exception:
            self._record_error("master role cycle failed")
        return self._transport_car.step()

    def request_state_sync(self, state: int, target: int, arg: int) -> int:
        """创建一条待确认状态同步请求

        @param state 状态编号
        @param target 目标编号
        @param arg 状态参数
        @return 本次同步序号
        """

        self._sync_seq = (self._sync_seq + 1) % 256
        self._pending_sync = {
            "seq": self._sync_seq,
            "state": int(state),
            "target": int(target),
            "arg": int(arg),
        }
        return self._sync_seq

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程"""

        self._process_uart3()
        self._process_uart8()
        self._send_pending_sync()

    def _process_uart3(self) -> None:
        """接管 UART3 按行读取并处理完整命令"""

        self._read_uart_lines(self._transport_car.uart3, "_rx_buf3", self._handle_uart3_line)

    def _process_uart8(self) -> None:
        """接管 UART8 按行读取确认与回报短包"""

        uart8 = self._transport_car.uart8
        if getattr(uart8, "any", None) is None:
            return
        self._read_uart_lines(uart8, "_rx_buf8", self._handle_uart8_line)

    def _read_uart_lines(self, uart, buffer_name: str, handler) -> None:
        buf_len = uart.any()
        if not buf_len:
            return
        try:
            setattr(self, buffer_name, getattr(self, buffer_name) + uart.read(buf_len).decode())
        except Exception:
            self._record_error("uart read failed")
            return
        while True:
            buffer = getattr(self, buffer_name)
            idx = buffer.find("\n")
            if idx == -1:
                return
            line = buffer[:idx].rstrip("\r").strip()
            setattr(self, buffer_name, buffer[idx + 1 :])
            handler(line)

    def _handle_uart3_line(self, line: str) -> None:
        """处理单条 UART3 原始输入行

        @param line 原始输入行
        """

        if not line:
            return
        packet = parse_short_packet(line)
        if packet is not None and packet.get("type") == "v":
            self._apply_velocity_packet(packet, source="uart3")
            self._write_forward_line(
                format_velocity_packet(packet["vx"], packet["vy"], packet["omega"])
                if packet.get("has_omega")
                else format_velocity_packet(packet["vx"], packet["vy"])
            )
            return
        if line.lower().startswith("v,"):
            self._record_error("invalid velocity packet")
            return
        self._transport_car._handle_uart_line(line, source="uart3")

    def _handle_uart8_line(self, line: str) -> None:
        """处理 UART8 回传短包

        @param line 原始输入行
        """

        packet = parse_short_packet(line)
        if packet is None:
            return
        if packet.get("type") == "a":
            pending = self._pending_sync
            if pending is not None and int(packet["seq"]) == int(pending["seq"]):
                self._pending_sync = None
        elif packet.get("type") == "r":
            self.last_report = packet

    def _apply_velocity_packet(self, packet: dict, source: str) -> None:
        handler = getattr(self._transport_car, "handle_velocity_packet", None)
        omega = float(packet.get("omega", 0.0))
        if handler is not None:
            handler(float(packet["vx"]), float(packet["vy"]), omega, source=source, has_omega=bool(packet.get("has_omega")))
            return
        self._transport_car.last_cmd["vx"] = float(packet["vx"])
        self._transport_car.last_cmd["vy"] = float(packet["vy"])
        self._transport_car.last_cmd["omega"] = omega
        finalize = getattr(self._transport_car, "_finalize_route", None)
        if finalize is not None:
            finalize({"vx", "vy", "omega"} if packet.get("has_omega") else {"vx", "vy"})

    def _send_pending_sync(self) -> None:
        pending = self._pending_sync
        if pending is None:
            return
        self._write_forward_line(
            "s,%d,%d,%d,%d"
            % (pending["seq"], pending["state"], pending["target"], pending["arg"])
        )

    def _write_forward_line(self, line: str) -> None:
        """把短包写到 UART8 主辅通信链路

        @param line 要转发的短包文本
        """

        try:
            self._transport_car.uart8.write("%s\r\n" % line)
        except Exception:
            self._record_error("uart8 forward write failed")

    def _record_error(self, text: str) -> None:
        """记录最小错误文本供联调使用

        @param text 错误描述
        """

        self._last_error_text = text
        self._transport_car.last_exception_text = text

    @staticmethod
    def _noop_transport_uart() -> None:
        """屏蔽共享底盘自己的 UART3 消费入口"""

        return None
