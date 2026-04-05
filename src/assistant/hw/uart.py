"""辅车 UART 薄封装.

@file src/assistant/hw/uart.py
"""

_package_name = str(globals().get("__package__", ""))

if "." in _package_name:
    from ..config import UART_BAUDRATE, UART_IDS
else:
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
        """按需创建并初始化 UART 设备.

        @brief 首次使用时完成串口实例化和波特率配置。
        """

        if self._device is None:
            from machine import UART

            self._device = UART(self.uart_id)
            self._device.init(self.baudrate)
        return self._device

    def read(self, size=None):
        """读取当前串口缓存数据.

        @brief 未指定长度时优先按当前可读字节数一次性取完。
        """

        device = self.ensure_device()
        if size is None:
            available = getattr(device, "any", lambda: 0)()
            if not available:
                return None
            return device.read(available)
        return device.read(size)

    def write(self, payload):
        """向串口写入原始负载.

        @brief 保持上层协议层自行决定报文编码格式。
        """

        device = self.ensure_device()
        return device.write(payload)

    def read_line(self):
        """读取一行以换行符结尾的文本.

        @brief 用内部缓冲把分片到达的串口内容重新拼成完整行。
        """

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
        """按 CRLF 结尾写出一行文本.

        @brief 统一辅车文本协议常用的逐行发送口径。
        """

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
