"""
@file src/vision/master/forward_runtime.py
@brief 主车角色运行时主体
"""

from config import params as _params
from protocol import link as protocol_link
from protocol.packet import (
    format_ack_packet,
    format_state_sync_packet,
    parse_short_packet,
)
from vision.master.state_machine import (
    IDLE,
    OBJECT_FOUND,
    SEARCH_OBJECT,
    MasterSearchStateMachine,
)


class MasterForwardRuntime:
    """
    @brief 基于共享底盘装配主车角色运行时外观

    @details 接管 UART3 前馈、UART8 转发、UART6 视觉 hook 和搜索状态机
    """

    def __init__(self, now_ms=None) -> None:
        """
        @brief 初始化主车角色运行时

        @param now_ms 毫秒时钟函数, None 时使用默认时钟
        """

        from core.runtime import TransportCar
        import hardware.uart_bus as uart_bus

        car = TransportCar()
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._uart6 = uart_bus.create_uart6()
        self._rx_buf3 = ""
        self._rx_buf6 = ""
        self._last_error_text = "none"
        self._now_ms = now_ms or protocol_link.default_now_ms
        self._uart3_velocity_this_cycle = False
        self._search = MasterSearchStateMachine(
            _params.MASTER_SEARCH_VX,
            _params.MASTER_SEARCH_VY,
            _params.MASTER_SEARCH_HOOK_CONFIG_ID,
        )
        self._pending_vision_sync = None
        self._pending_vision_sync_last_sent_ms = None
        self._reliable_write_this_cycle = False

        if getattr(car, "_process_uart", None) is not None:
            car._process_uart = self._noop_transport_uart

    @property
    def search_state(self):
        """
        @brief 返回主车搜索状态编号

        @return 当前搜索状态编号
        """

        return self._search.state

    @property
    def search_transition_count(self):
        """
        @brief 返回主车搜索状态迁移次数

        @return 搜索状态迁移次数
        """

        return self._search.transition_count

    def start_search(self):
        """
        @brief 显式启动主车物体搜索并创建视觉 hook 同步上下文

        @return hook 同步字段字典, 无需启动时返回当前同步字段或 None
        """

        if self._search.state == SEARCH_OBJECT:
            return self._search.search_sync
        sync = self._search.enter_search()
        if sync is not None:
            self._pending_vision_sync = sync
            self._pending_vision_sync_last_sent_ms = None
        return sync

    def mark_tick(self, tick=None) -> None:
        """
        @brief 转发 ticker 中断标记

        @param tick 节拍值
        """

        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        """
        @brief 转发 ticker 对象

        @param ticker_obj ticker 对象
        """

        self._transport_car.set_ticker(ticker_obj)

    def step(self) -> bool:
        """
        @brief 执行一拍主车角色运行时

        @return 是否继续运行
        """

        try:
            self._run_role_cycle()
        except Exception:
            self._record_error("master role cycle failed")
        return self._transport_car.step()

    def _run_role_cycle(self) -> None:
        """
        @brief 执行角色层单拍流程
        """

        self._uart3_velocity_this_cycle = False
        self._reliable_write_this_cycle = False
        self._ensure_search_started()
        self._process_uart3()
        self._process_uart6()
        self._send_pending_vision_sync()
        self._write_search_velocity()

    def _ensure_search_started(self) -> None:
        """
        @brief 确保主车搜索状态机进入搜索态
        """

        if self._search.state == IDLE:
            self.start_search()

    def _process_uart3(self) -> None:
        """
        @brief 接管 UART3 按行读取并处理短包输入
        """

        self._read_uart_lines(self._transport_car.uart3, "_rx_buf3", self._handle_uart3_line)

    def _process_uart6(self) -> None:
        """
        @brief 接管 UART6 按行读取视觉短包, 同拍观测只保留最新帧
        """

        buf_len = self._uart6.any()
        if not buf_len:
            return
        try:
            self._rx_buf6 += self._uart6.read(buf_len).decode()
        except Exception:
            self._record_error("uart read failed")
            return

        latest_observation = None
        while True:
            idx = self._rx_buf6.find("\n")
            if idx == -1:
                break
            line = self._rx_buf6[:idx].rstrip("\r").strip()
            self._rx_buf6 = self._rx_buf6[idx + 1 :]
            packet = parse_short_packet(line)
            if packet is None:
                continue
            packet_type = packet.get("type")
            if packet_type == "o":
                latest_observation = packet
            else:
                self._handle_uart6_packet(packet)
        if latest_observation is not None:
            self._search.handle_observation(latest_observation)

    def _read_uart_lines(self, uart, buffer_name: str, handler) -> None:
        """
        @brief 从指定串口读取完整文本行并交给处理函数

        @param uart 串口对象
        @param buffer_name 接收缓冲区属性名
        @param handler 单行文本处理函数
        """

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
        """
        @brief 处理单条 UART3 短包输入行

        @param line 原始输入行
        """

        if not line:
            return
        packet = parse_short_packet(line)
        if packet is not None and packet.get("type") == "v":
            self._apply_velocity_packet(packet, source="uart3")
            self._uart3_velocity_this_cycle = True
            self._write_forward_line(line)
            return
        if line.lower().startswith("v,"):
            self._record_error("invalid velocity packet")

    def _handle_uart6_line(self, line: str) -> None:
        """
        @brief 处理 UART6 本地视觉短包

        @param line 原始输入行
        """

        packet = parse_short_packet(line)
        if packet is None:
            return
        self._handle_uart6_packet(packet)

    def _handle_uart6_packet(self, packet: dict) -> None:
        """
        @brief 处理已经解析完成的 UART6 本地视觉短包

        @param packet 解析后的视觉短包字典
        """

        packet_type = packet.get("type")
        if packet_type == "a":
            self._handle_vision_ack_packet(packet)
        elif packet_type == "o":
            self._search.handle_observation(packet)
        elif packet_type == "r":
            self._handle_vision_event_packet(packet)

    def _handle_vision_ack_packet(self, packet: dict) -> None:
        """
        @brief 处理视觉端可靠包确认

        @param packet 解析后的确认短包
        """

        pending = self._pending_vision_sync
        if pending is not None and int(packet["reliable_seq"]) == int(pending["reliable_seq"]):
            self._pending_vision_sync = None
            self._pending_vision_sync_last_sent_ms = None

    def _handle_vision_event_packet(self, packet: dict) -> None:
        """
        @brief 处理视觉端可靠事件包

        @param packet 解析后的事件短包
        """

        reliable_seq = int(packet["reliable_seq"])
        self._write_reliable_line_to(
            self._uart6,
            format_ack_packet(reliable_seq),
            "uart6 reliable write failed",
        )
        if self._search.handle_event(packet):
            self._pending_vision_sync = None
            self._pending_vision_sync_last_sent_ms = None

    def _apply_velocity_packet(self, packet: dict, source: str) -> None:
        """
        @brief 将速度短包写入共享底盘速度入口

        @param packet 解析后的速度短包
        @param source 速度来源标识
        """

        omega = float(packet.get("omega", 0.0))
        self._transport_car.handle_velocity_packet(
            float(packet["vx"]),
            float(packet["vy"]),
            omega,
            source=source,
            has_omega=bool(packet.get("has_omega")),
        )

    def _send_pending_vision_sync(self) -> None:
        """
        @brief 按可靠发送节奏发送待确认的视觉 hook 同步包
        """

        pending = self._pending_vision_sync
        if pending is None:
            return
        if self._reliable_write_this_cycle:
            return
        now_ms = self._now_ms()
        if not protocol_link.should_resend(
            now_ms,
            self._pending_vision_sync_last_sent_ms,
            _params.RELIABLE_RESEND_INTERVAL_MS,
        ):
            return
        self._write_reliable_line_to(
            self._uart6,
            format_state_sync_packet(
                pending["reliable_seq"],
                pending["context_id"],
                pending["state"],
                pending["target"],
                pending["arg"],
            ),
            "uart6 reliable write failed",
        )
        self._pending_vision_sync_last_sent_ms = now_ms

    def _write_search_velocity(self) -> None:
        """
        @brief 将当前搜索状态机速度写入共享底盘
        """

        if self._search.state == IDLE:
            return
        if self._uart3_velocity_this_cycle:
            return
        vx, vy = self._search.build_velocity()
        self._transport_car.handle_velocity_packet(
            vx,
            vy,
            0.0,
            source="master_search",
            has_omega=False,
        )

    def _write_forward_line(self, line: str) -> None:
        """
        @brief 把短包写到 UART8 主辅通信链路

        @param line 要转发的短包文本
        """

        try:
            protocol_link.write_data_line(self._transport_car.uart8, line)
        except Exception:
            self._record_error("uart8 forward write failed")

    def _write_reliable_line_to(self, uart, line: str, error_text: str) -> bool:
        """
        @brief 把可靠短包写到指定链路

        @param uart 目标串口对象
        @param line 不含行尾的可靠短包文本
        @param error_text 写出失败时记录的错误文本
        @return 是否完整写出整行短包
        """

        try:
            wrote_all = protocol_link.write_reliable_line(uart, line)
            self._reliable_write_this_cycle = True
            return wrote_all
        except Exception:
            self._record_error(error_text)
            return False

    def _record_error(self, text: str) -> None:
        """
        @brief 记录最小错误文本供联调使用

        @param text 错误描述
        """

        self._last_error_text = text
        self._transport_car.last_exception_text = text

    @staticmethod
    def _noop_transport_uart() -> None:
        """
        @brief 屏蔽共享底盘自己的 UART3 消费入口
        """

        return None
