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
except ModuleNotFoundError as exc:
    if exc.name != "assistant":
        raise
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
        if app is None:
            app = AssistantApp(hw_bundle=hw_bundle)
        app_hw_bundle = self._resolve_app_hw_bundle(app)
        if app_hw_bundle is not hw_bundle:
            raise ValueError("hw_bundle 与 app 必须引用同一套装配")
        self.hw_bundle = app_hw_bundle
        self.app = app

    @staticmethod
    def _resolve_app_hw_bundle(app):
        runtime = getattr(app, "runtime", None)
        runtime_hw_bundle = getattr(runtime, "hw_bundle", None)
        core = getattr(runtime, "core", None)
        core_hw_bundle = getattr(core, "hw_bundle", None)
        app_hw_bundle = getattr(app, "hw_bundle", None)
        bundles = []
        for candidate in (core_hw_bundle, runtime_hw_bundle, app_hw_bundle):
            if candidate is None:
                continue
            if all(existing is not candidate for existing in bundles):
                bundles.append(candidate)
        if len(bundles) > 1:
            raise ValueError("app 必须暴露唯一 hw_bundle owner")
        if core_hw_bundle is not None:
            return core_hw_bundle
        if runtime_hw_bundle is not None:
            return runtime_hw_bundle
        if app_hw_bundle is not None:
            return app_hw_bundle
        raise ValueError("app 必须暴露唯一 hw_bundle owner")

    def step(self, now_ms):
        uart3 = self.hw_bundle["uart"]["uart3"]
        line = uart3.read_line()
        if line:
            reply = self.app.handle_line(line, now_ms=now_ms)
            if reply:
                uart3.write_line(reply)

        tick_reply = self.app.tick(now_ms=now_ms)
        if tick_reply:
            uart3.write_line(tick_reply)
        return tick_reply


class AssistantApp:
    """负责串联协议解析和执行运行时

    @brief 对外提供辅车命令处理和周期推进入口
    """

    def __init__(self, timeout_ms=None, hw_bundle=None):
        if timeout_ms is None:
            timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
        if hw_bundle is None:
            hw_bundle = build_hw_bundle()
        self.hw_bundle = hw_bundle
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
