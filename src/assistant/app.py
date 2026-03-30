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
        self._timeout_reported = False

    def _render_ack(self):
        """生成对外确认回包

        @brief 辅助入口统一返回带最近序号的确认文本
        @return str
        """

        return "ACK,last_seq=%d" % int(self.runtime.state.last_seq)

    def _render_timeout(self):
        """生成对外超时回包

        @brief 周期检查发现跟随链路超时时明确对外报告
        @return str
        """

        return "TIMEOUT,last_seq=%d" % int(self.runtime.state.last_seq)

    def handle_line(self, line, now_ms):
        """处理一条主车输入

        @brief 解析文本协议并交给运行时执行
        @param line 原始命令文本
        @param now_ms 当前毫秒时间
        @return str
        """

        try:
            command = parse_command(line)
        except (TypeError, ValueError):
            return "ERR"
        reply = self.runtime.apply_command(command, now_ms=now_ms)

        if not bool(self.runtime.state.timeout):
            self._timeout_reported = False

        if command.kind == "state_query" or str(reply) == "ERR":
            return str(reply)
        if command.kind == "follow":
            return ""
        return self._render_ack()

    def tick(self, now_ms):
        """推进辅车应用循环

        @brief 触发周期性安全检查和状态推进
        @param now_ms 当前毫秒时间
        @return str
        """

        reply = self.runtime.tick(now_ms=now_ms)
        if not bool(self.runtime.state.timeout):
            self._timeout_reported = False
        if (
            str(reply) == "DONE"
            and bool(self.runtime.state.timeout)
            and not self._timeout_reported
        ):
            self._timeout_reported = True
            return self._render_timeout()
        return ""
