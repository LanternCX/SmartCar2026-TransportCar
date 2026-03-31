"""辅车应用编排入口

@file src/assistant/app.py
"""

try:
    import assistant.runtime_params as runtime_params
    from assistant.ctrl.chassis import ChassisRuntime
    from assistant.protocol import parse_command
    from assistant.hw.encoders import build_encoder_bundle
    from assistant.hw.imu import build_imu_bundle
    from assistant.hw.motors import build_motor_bundle
    from assistant.hw.uart import build_uart_bundle
except ImportError:
    import runtime_params
    from ctrl.chassis import ChassisRuntime
    from protocol import parse_command
    from hw.encoders import build_encoder_bundle
    from hw.imu import build_imu_bundle
    from hw.motors import build_motor_bundle
    from hw.uart import build_uart_bundle


def build_hw_bundle():
    """构造辅车硬件装配入口.

    @brief 当前阶段先收口已存在的新框架硬件边界对象。
    @return dict
    """

    return {
        "uart": build_uart_bundle(),
        "motors": build_motor_bundle(),
        "encoders": build_encoder_bundle(),
        "imu": build_imu_bundle(),
    }


class AssistantRuntimeLoop:
    """辅车当前主线运行循环.

    @brief 串起 UART3 收包、执行与最小状态回传。
    """

    def __init__(self, hw_bundle, app=None):
        self.hw_bundle = hw_bundle
        self.app = app or AssistantApp()
        if hasattr(self.app.runtime, "core"):
            self.app.runtime.core.hw_bundle = hw_bundle

    def step(self, now_ms):
        line = self.hw_bundle["uart3"].read_line()
        if line:
            reply = self.app.handle_line(line, now_ms=now_ms)
            if reply:
                self.hw_bundle["uart3"].write_line(reply)

        tick_reply = self.app.tick(now_ms=now_ms)
        if tick_reply:
            self.hw_bundle["uart3"].write_line(tick_reply)
        return tick_reply


class AssistantApp:
    """负责串联协议解析和执行运行时

    @brief 对外提供辅车命令处理和周期推进入口
    """

    def __init__(self, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
        self.hw_bundle = build_hw_bundle()
        # 应用层只保留一个运行时对象, 统一收口命令执行和状态维护
        self.runtime = ChassisRuntime(timeout_ms=timeout_ms, hw_bundle=self.hw_bundle)
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
