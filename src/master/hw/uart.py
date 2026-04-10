"""主车 UART 薄封装.

@file src/master/hw/uart.py
"""

_package_name = str(globals().get("__package__", ""))

if "." in _package_name:
    from ..config import UART_BAUDRATE, UART_IDS
else:
    from config import UART_BAUDRATE, UART_IDS


UART_LINE_LIMITS = {
    "uart3": 256,
    "uart6": 160,
    "uart8": 160,
}
UART_READ_CHUNKS = {
    "uart3": 96,
    "uart6": 96,
    "uart8": 96,
}


class UartPort:
    """串口端口描述.

    @brief 当前阶段先统一暴露串口 id 与波特率。
    """

    def __init__(self, name, uart_id, baudrate):
        self.name = str(name)
        self.uart_id = int(uart_id)
        self.baudrate = int(baudrate)
        self._device = None
        self._read_buffer = bytearray()
        self._discard_until_newline = False
        self._line_limit = UART_LINE_LIMITS.get(self.name)
        self._read_chunk_size = UART_READ_CHUNKS.get(self.name)

    @staticmethod
    def _find_newline(payload):
        for index, value in enumerate(payload):
            if value == 10:
                return index
        return -1

    def _tail_length(self):
        """返回缓冲区末尾未成行内容长度

        @brief 用于判断继续拼接后是否会让当前半行超过长度上限。
        @return int
        """

        last_newline = -1
        for index, value in enumerate(self._read_buffer):
            if value == 10:
                last_newline = index
        if last_newline < 0:
            tail_length = len(self._read_buffer)
        else:
            tail_length = len(self._read_buffer) - last_newline - 1
        if tail_length > 0 and self._read_buffer[-1] == 13:
            tail_length -= 1
        return tail_length

    def _drop_partial_tail(self):
        last_newline = -1
        for index, value in enumerate(self._read_buffer):
            if value == 10:
                last_newline = index
        if last_newline < 0:
            self._read_buffer[:] = b""
            return
        self._read_buffer[last_newline + 1 :] = b""

    def _append_payload(self, payload):
        """把新读到的字节流并入按行缓冲区

        @brief 在保留完整行的同时丢弃超长半行, 避免视觉和命令链被异常报文拖住。
        @param payload 新读到的串口负载
        """

        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        elif not isinstance(payload, bytes):
            payload = bytes(payload)
        if self._line_limit is None:
            self._read_buffer.extend(payload)
            return

        index = 0
        payload_length = len(payload)
        while index < payload_length:
            if self._discard_until_newline:
                newline_index = payload.find(b"\n", index)
                if newline_index < 0:
                    return
                self._discard_until_newline = False
                index = newline_index + 1
                continue

            newline_index = payload.find(b"\n", index)
            if newline_index < 0:
                tail = payload[index:]
                tail_length = len(tail)
                if tail_length > 0 and tail[-1] == 13:
                    tail_length -= 1
                if self._tail_length() + tail_length > self._line_limit:
                    self._drop_partial_tail()
                    self._discard_until_newline = True
                    return
                self._read_buffer.extend(tail)
                return

            line_chunk = payload[index : newline_index + 1]
            line_body_length = newline_index - index
            if line_body_length > 0 and payload[newline_index - 1] == 13:
                line_body_length -= 1
            if self._tail_length() + line_body_length > self._line_limit:
                self._drop_partial_tail()
                index = newline_index + 1
                continue
            self._read_buffer.extend(line_chunk)
            index = newline_index + 1

    def _pop_ready_line(self):
        newline_index = self._find_newline(self._read_buffer)
        if newline_index < 0:
            return None
        line = bytes(self._read_buffer[:newline_index])
        self._read_buffer[: newline_index + 1] = b""
        return line.decode("utf-8").strip("\r")

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
            if self._read_chunk_size is not None:
                available = min(int(available), int(self._read_chunk_size))
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
            self._append_payload(payload)
        return self._pop_ready_line()

    def write_line(self, payload):
        """按 CRLF 结尾写出一行文本.

        @brief 协议输出统一走这一层, 保持板端与主机侧格式一致。
        """

        if isinstance(payload, bytearray):
            payload = bytes(payload)
        elif not isinstance(payload, (bytes, str)):
            payload = str(payload)

        written = self.write(payload)
        newline = b"\r\n" if isinstance(payload, bytes) else "\r\n"
        tail_written = self.write(newline)
        if isinstance(written, int) and isinstance(tail_written, int):
            return written + tail_written
        if tail_written is not None:
            return tail_written
        return written


def build_uart_bundle():
    """构造主车串口描述集合.

    @brief 先收口已确认的 UART3/UART6/UART8 事实。
    @return dict
    """

    bundle = {}
    for name, uart_id in UART_IDS.items():
        bundle[name] = UartPort(name=name, uart_id=uart_id, baudrate=UART_BAUDRATE)
    return bundle
