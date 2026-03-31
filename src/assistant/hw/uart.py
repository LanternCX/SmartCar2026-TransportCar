"""辅车 UART 薄封装.

@file src/assistant/hw/uart.py
"""

try:
    from assistant.config import UART_BAUDRATE, UART_IDS
except ImportError:
    from config import UART_BAUDRATE, UART_IDS


class UartPort:
    """串口端口描述.

    @brief 当前阶段先统一暴露串口 id 与波特率。
    """

    def __init__(self, name, uart_id, baudrate):
        self.name = str(name)
        self.uart_id = int(uart_id)
        self.baudrate = int(baudrate)
        self._device = None
        self._read_buffer = ""

    def ensure_device(self):
        if self._device is None:
            from machine import UART

            self._device = UART(self.uart_id)
            self._device.init(self.baudrate)
        return self._device

    def read(self, size=None):
        device = self.ensure_device()
        if size is None:
            available = getattr(device, "any", lambda: 0)()
            if not available:
                return None
            return device.read(available)
        return device.read(size)

    def write(self, payload):
        device = self.ensure_device()
        return device.write(payload)

    def read_line(self):
        payload = self.read()
        if payload is not None:
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            self._read_buffer += str(payload)
        if "\n" not in self._read_buffer:
            return None
        line, self._read_buffer = self._read_buffer.split("\n", 1)
        return line.strip("\r")

    def write_line(self, payload):
        return self.write("%s\r\n" % str(payload))


def build_uart_bundle():
    """构造辅车串口描述集合.

    @brief 先收口已确认的 UART3 事实。
    @return dict
    """

    bundle = {}
    for name, uart_id in UART_IDS.items():
        bundle[name] = UartPort(name=name, uart_id=uart_id, baudrate=UART_BAUDRATE)
    return bundle
