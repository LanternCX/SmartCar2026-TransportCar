"""辅车 UART 薄封装.

@file src/assistant/hw/uart.py
"""

_package_name = str(globals().get("__package__", ""))

if "." in _package_name:
    from ..config import UART_BAUDRATE, UART_IDS
else:
    from config import UART_BAUDRATE, UART_IDS


UART_LINE_LIMITS = {
    "uart3": 256,
}
UART_READ_CHUNKS = {
    "uart3": 96,
}
UART_READ_BUDGET_CHUNKS = {}


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
        self._read_budget_chunks = UART_READ_BUDGET_CHUNKS.get(self.name)

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

        @brief 在保留完整行的同时丢弃超长半行, 避免命令链被异常报文拖住。
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

        @brief 未指定长度时优先按当前可读字节数分块读取, 避免单拍直接吞下过大缓存。
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
            self._append_payload(payload)
        return self._pop_ready_line()

    def read_latest_line(self, transform=None):
        """尽量清掉积压输入, 但只返回最新一条完整文本行.

        @brief 控制链只关心最新命令, 这里把完整积压行在同拍内尽量清空, 避免旧消息继续堆积。
        """

        latest = None
        while True:
            line = self._pop_ready_line()
            if line is None:
                break
            if transform is None:
                latest = line
                continue
            transformed = transform(line)
            if transformed is not None:
                latest = transformed
        read_count = 0
        while True:
            if (
                self._read_budget_chunks is not None
                and read_count >= self._read_budget_chunks
            ):
                break
            payload = self.read()
            if payload is None:
                break
            read_count += 1
            self._append_payload(payload)
            while True:
                line = self._pop_ready_line()
                if line is None:
                    break
                if transform is None:
                    latest = line
                    continue
                transformed = transform(line)
                if transformed is not None:
                    latest = transformed
        return latest

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
