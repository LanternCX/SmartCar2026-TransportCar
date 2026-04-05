"""主车 UART 薄封装.

@file src/master/hw/uart.py
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
        """按需创建并初始化串口对象.

        @brief 串口波特率和编号都在这里一次性落地, 上层只保留收发语义。
        """

        if self._device is None:
            from machine import UART

            self._device = UART(self.uart_id)
            self._device.init(self.baudrate)
        return self._device

    def read(self, size=None):
        """读取串口字节流.

        @brief 未指定长度时先按 `any()` 读取当前可用数据, 避免阻塞主循环。
        """

        device = self.ensure_device()
        if size is None:
            available = getattr(device, "any", lambda: 0)()
            if not available:
                return None
            return device.read(available)
        return device.read(size)

    def write(self, payload):
        """写出原始串口负载.

        @brief 协议层负责组织内容, 这里仅保持最薄的发送封装。
        """

        device = self.ensure_device()
        return device.write(payload)

    def read_line(self):
        """按换行符切出一条完整文本行.

        @brief 内部保留残留缓冲, 让视觉和命令链都能按行消费串口文本。
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

        @brief 协议输出统一走这一层, 保持板端与主机侧格式一致。
        """

        return self.write("%s\r\n" % str(payload))


def build_uart_bundle():
    """构造主车串口描述集合.

    @brief 先收口已确认的 UART3/UART6/UART8 事实。
    @return dict
    """

    bundle = {}
    for name, uart_id in UART_IDS.items():
        bundle[name] = UartPort(name=name, uart_id=uart_id, baudrate=UART_BAUDRATE)
    return bundle
