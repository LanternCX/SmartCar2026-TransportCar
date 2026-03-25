"""辅车最小应用定义

@file src/assistant/app.py
"""

from assistant.motion_runtime import MotionRuntime
from assistant.protocol import parse_command


class AssistantApp:
    """辅车最小应用壳

    @brief 为后续辅车运行时预留最小入口
    """

    def __init__(self, timeout_ms: int = 250) -> None:
        self.runtime = MotionRuntime(timeout_ms=timeout_ms)

    def handle_line(self, line: str, now_ms: int) -> str:
        """处理一条主车输入

        @brief 解析文本协议并交给最小执行运行时
        @param line 原始命令文本
        @param now_ms 当前毫秒时间
        @return str
        """

        command = parse_command(line)
        return self.runtime.apply_command(command, now_ms=now_ms)

    def tick(self, now_ms: int) -> str:
        """推进最小应用循环

        @brief 主要用于超时停机检查
        @param now_ms 当前毫秒时间
        @return str
        """

        return self.runtime.tick(now_ms=now_ms)
