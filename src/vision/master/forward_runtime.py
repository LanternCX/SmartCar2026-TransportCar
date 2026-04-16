"""主车角色运行时主体.

@file src/vision/master/forward_runtime.py
"""

import math

from config import params as _params


V_CMD_MAX = getattr(_params, "V_CMD_MAX")


def _is_velocity_key(key: str) -> bool:
    """判断字段名是否属于当前允许转发的速度字段."""

    return key in ("vx", "vy", "omega", "w")


def _canonical_velocity_key(key: str) -> str:
    """把速度字段别名收口成辅车当前统一消费的字段名."""

    if key == "w":
        return "omega"
    return key


class MasterForwardRuntime:
    """基于共享底盘装配主车角色运行时外观.

    @brief 在共享底盘外层接管 UART3, 并把速度字段转发到 UART8
    """

    def __init__(self) -> None:
        from core.runtime import TransportCar

        car = TransportCar()
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._rx_buf3 = ""
        self._last_error_text = "none"

        if getattr(car, "_process_uart", None) is not None:
            # UART3 已由主车角色层接管, 共享底盘不再重复读取
            car._process_uart = self._noop_transport_uart

    def mark_tick(self, tick=None) -> None:
        """转发 ticker 中断标记."""

        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        """转发 ticker 对象."""

        self._transport_car.set_ticker(ticker_obj)

    def step(self) -> bool:
        """执行一拍主车角色运行时."""

        try:
            self._run_role_cycle()
        except Exception:
            self._record_error("master role cycle failed")
        return self._transport_car.step()

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程."""

        self._process_uart3()

    def _process_uart3(self) -> None:
        """接管 UART3 按行读取并处理完整命令."""

        uart3 = self._transport_car.uart3
        buf_len = uart3.any()
        if not buf_len:
            return

        try:
            self._rx_buf3 += uart3.read(buf_len).decode()
        except Exception:
            self._record_error("uart3 read failed")
            return

        while True:
            idx = self._rx_buf3.find("\n")
            if idx == -1:
                return
            line = self._rx_buf3[:idx].rstrip("\r").strip()
            self._rx_buf3 = self._rx_buf3[idx + 1 :]
            self._handle_uart3_line(line)

    def _handle_uart3_line(self, line: str) -> None:
        """处理单条 UART3 原始命令行."""

        if not line:
            return

        forward_line = self._extract_forward_line(line)
        if forward_line:
            self._write_forward_line(forward_line)
        self._transport_car._handle_uart_line(line, source="uart3")

    def _extract_forward_line(self, line: str) -> str:
        """从原始命令中抽取可转发的速度字段文本."""

        text = line.strip()
        if not text or text.startswith("?"):
            return ""

        fields = {}
        for fragment in text.split(","):
            item = fragment.strip()
            if not item or "=" not in item:
                continue
            key_text, value_text = item.split("=", 1)
            key = key_text.strip().lower()
            value = value_text.strip()
            if not _is_velocity_key(key):
                continue
            try:
                numeric_value = float(value)
            except ValueError:
                self._record_error("invalid velocity field: %s=%s" % (key, value))
                return ""
            if not math.isfinite(numeric_value):
                self._record_error("invalid velocity field: %s=%s" % (key, value))
                return ""
            if numeric_value < -V_CMD_MAX or numeric_value > V_CMD_MAX:
                self._record_error("invalid velocity field: %s=%s" % (key, value))
                return ""
            fields[_canonical_velocity_key(key)] = value

        ordered_fields = []
        for key in ("vx", "vy", "omega"):
            value = fields.get(key)
            if value is not None:
                ordered_fields.append("%s=%s" % (key, value))
        return ",".join(ordered_fields)

    def _write_forward_line(self, line: str) -> None:
        """把速度转发行写到 UART8 主辅通信链路."""

        try:
            self._transport_car.uart8.write("%s\r\n" % line)
        except Exception:
            self._record_error("uart8 forward write failed")

    def _record_error(self, text: str) -> None:
        """记录最小错误文本供联调使用."""

        self._last_error_text = text
        self._transport_car.last_exception_text = text

    @staticmethod
    def _noop_transport_uart() -> None:
        """屏蔽共享底盘自己的 UART3 消费入口."""

        return None
