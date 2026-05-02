"""主车角色运行时主体

@file src/vision/master/forward_runtime.py
"""

from hardware.uart_bus import create_uart6
from vision.serial_protocol import format_velocity_packet, parse_short_packet


_UART6_INPUT_LIMIT = 128


class MasterForwardRuntime:
    """基于共享底盘装配主车角色运行时外观

    @brief 在共享底盘外层接管 UART3 与本车 UART6, 并把当前底盘速度转发到 UART8
    """

    def __init__(self) -> None:
        from core.runtime import TransportCar

        car = TransportCar()
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._uart6 = create_uart6()
        self._rx_buf3 = ""
        self._rx_buf6 = ""
        self._rx_buf8 = ""
        self._latest_uart6_velocity = None
        self._uart3_velocity_received_this_tick = False
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

        self._uart3_velocity_received_this_tick = False
        self._process_uart3()
        self._process_uart6()
        if not self._uart3_velocity_received_this_tick:
            self._apply_latest_uart6_velocity()
        self._forward_current_chassis_velocity()
        self._process_uart8()
        self._send_pending_sync()

    def _process_uart3(self) -> None:
        """接管 UART3 按行读取并处理短包输入"""

        self._read_uart_lines(self._transport_car.uart3, "_rx_buf3", self._handle_uart3_line)

    def _process_uart6(self) -> None:
        """接管 UART6 按行读取本车视觉速度输入"""

        self._read_uart_lines(
            self._uart6,
            "_rx_buf6",
            self._handle_uart6_line,
            read_error_text="uart6 read failed",
            overflow_error_text="invalid uart6 input",
            input_limit=_UART6_INPUT_LIMIT,
        )

    def _process_uart8(self) -> None:
        """接管 UART8 按行读取确认与回报短包"""

        uart8 = self._transport_car.uart8
        if getattr(uart8, "any", None) is None:
            return
        self._read_uart_lines(uart8, "_rx_buf8", self._handle_uart8_line)

    def _read_uart_lines(
        self,
        uart,
        buffer_name: str,
        handler,
        read_error_text: str = "uart read failed",
        overflow_error_text=None,
        input_limit=None,
    ) -> None:
        while True:
            buf_len = uart.any()
            if not buf_len:
                return
            input_overflow = input_limit is not None and buf_len > input_limit
            if input_overflow:
                buf_len = input_limit
            try:
                chunk = uart.read(buf_len).decode()
            except Exception:
                self._record_error(read_error_text)
                return
            setattr(self, buffer_name, getattr(self, buffer_name) + chunk)
            if input_overflow:
                setattr(self, buffer_name, "")
                if overflow_error_text is not None:
                    self._record_error(overflow_error_text)
                return
            if self._drain_uart_lines(buffer_name, handler, overflow_error_text, input_limit):
                return

    def _drain_uart_lines(self, buffer_name: str, handler, overflow_error_text, input_limit) -> bool:
        while True:
            buffer = getattr(self, buffer_name)
            if input_limit is not None and len(buffer) > input_limit:
                setattr(self, buffer_name, "")
                if overflow_error_text is not None:
                    self._record_error(overflow_error_text)
                return True
            idx = buffer.find("\n")
            if idx == -1:
                return False
            if input_limit is not None and idx > input_limit:
                setattr(self, buffer_name, buffer[idx + 1 :])
                if overflow_error_text is not None:
                    self._record_error(overflow_error_text)
                continue
            line = buffer[:idx].rstrip("\r").strip()
            setattr(self, buffer_name, buffer[idx + 1 :])
            handler(line)

    def _handle_uart3_line(self, line: str) -> None:
        """处理单条 UART3 短包输入行

        @param line 原始输入行
        """

        if not line:
            return
        packet = parse_short_packet(line)
        if packet is not None and packet.get("type") == "v":
            self._apply_velocity_packet(packet, source="uart3")
            self._uart3_velocity_received_this_tick = True
            return
        if line.lower().startswith("v,"):
            self._record_error("invalid velocity packet")

    def _handle_uart6_line(self, line: str) -> None:
        """处理单条 UART6 视觉速度输入行

        @param line 原始输入行
        """

        if not line:
            return
        packet = parse_short_packet(line)
        if packet is not None and packet.get("type") == "v":
            self._latest_uart6_velocity = packet
            return
        if line.lower().startswith("v,"):
            self._record_error("invalid uart6 velocity packet")

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

    def _apply_latest_uart6_velocity(self) -> None:
        packet = self._latest_uart6_velocity
        if packet is not None:
            self._apply_velocity_packet(packet, source="uart6", force_no_omega=True)

    def _forward_current_chassis_velocity(self) -> None:
        state = self._transport_car.control_state
        omega = state.get("omega")
        if omega is None:
            line = format_velocity_packet(state.get("vx", 0.0), state.get("vy", 0.0))
        else:
            line = format_velocity_packet(state.get("vx", 0.0), state.get("vy", 0.0), omega)
        self._write_forward_line(line)

    def _apply_velocity_packet(self, packet: dict, source: str, force_no_omega: bool = False) -> None:
        omega = 0.0 if force_no_omega else float(packet.get("omega", 0.0))
        self._transport_car.handle_velocity_packet(
            float(packet["vx"]),
            float(packet["vy"]),
            omega,
            source=source,
            has_omega=False if force_no_omega else bool(packet.get("has_omega")),
        )

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
