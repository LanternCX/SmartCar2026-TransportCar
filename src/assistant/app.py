"""辅车应用编排入口

@file src/assistant/app.py
"""

from config.params import FOLLOW_TIMEOUT_MS
from assistant.motion_runtime import MotionRuntime
from assistant.protocol import parse_command


class AssistantApp:
    """负责串联协议解析和执行运行时

    @brief 对外提供辅车命令处理和周期推进入口
    """

    def __init__(self, timeout_ms=FOLLOW_TIMEOUT_MS):
        # 应用层只保留一个运行时对象, 统一收口命令执行和状态维护
        self.runtime = MotionRuntime(timeout_ms=timeout_ms)

    def handle_line(self, line, now_ms):
        """处理一条主车输入

        @brief 解析文本协议并交给运行时执行
        @param line 原始命令文本
        @param now_ms 当前毫秒时间
        @return str
        """

        command = parse_command(line)
        return self.runtime.apply_command(command, now_ms=now_ms)

    def tick(self, now_ms):
        """推进辅车应用循环

        @brief 触发周期性安全检查和状态推进
        @param now_ms 当前毫秒时间
        @return str
        """

        return self.runtime.tick(now_ms=now_ms)
