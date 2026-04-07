"""辅车应用编排入口

@file src/assistant/app.py
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)

if _USE_DIRECT_IMPORTS:
    import runtime_params
    from hw.encoders import build_encoder_bundle
    from hw.imu import build_imu_bundle
    from hw.motors import build_motor_bundle
    from hw.uart import build_uart_bundle
    from motion_runtime import (
        apply_runtime_command,
        create_runtime_state,
        run_base_cycle,
    )
    from protocol import parse_command
else:
    from . import runtime_params
    from .hw.encoders import build_encoder_bundle
    from .hw.imu import build_imu_bundle
    from .hw.motors import build_motor_bundle
    from .hw.uart import build_uart_bundle
    from .motion_runtime import (
        apply_runtime_command,
        create_runtime_state,
        run_base_cycle,
    )
    from .protocol import parse_command


def _normalize_error_reason(error):
    reason = str(error).strip()
    if not reason:
        return "unknown"
    lowered = reason.lower()
    if "invalid literal for int" in lowered:
        return "invalid_literal_for_int"
    if "invalid literal for float" in lowered:
        return "invalid_literal_for_float"
    sanitized = []
    for char in lowered:
        if ("a" <= char <= "z") or ("0" <= char <= "9"):
            sanitized.append(char)
            continue
        sanitized.append("_")
    compact = "".join(sanitized).strip("_")
    while "__" in compact:
        compact = compact.replace("__", "_")
    return compact or "unknown"


def _render_error_reply(reason):
    return "ERR,reason=%s" % str(reason)


def _render_error_reply_with_raw(reason, raw_line):
    raw_text = str(raw_line).strip()
    if not raw_text:
        return _render_error_reply(reason)
    return "ERR,reason=%s,raw=%s" % (str(reason), raw_text)


def _render_follow_reply(command):
    return "K,%d,%d" % (int(command.seq), int(command.valid))


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
        runtime_state = getattr(app, "runtime_state", None)
        state_hw_bundle = getattr(runtime_state, "hw_bundle", None)
        app_hw_bundle = getattr(app, "hw_bundle", None)
        if (
            state_hw_bundle is not None
            and app_hw_bundle is not None
            and state_hw_bundle is not app_hw_bundle
        ):
            raise ValueError("app 必须暴露唯一 hw_bundle owner")
        if state_hw_bundle is not None:
            return state_hw_bundle
        if app_hw_bundle is not None:
            return app_hw_bundle
        raise ValueError("app 必须暴露唯一 hw_bundle owner")

    def step(self, now_ms):
        """推进一轮辅车串口与运行时循环

        @brief 同一轮里先处理串口来包, 再补一次周期检查和状态回传。
        @param now_ms 当前毫秒时间
        @return str
        """

        app_hw_bundle = self._resolve_app_hw_bundle(self.app)
        if app_hw_bundle is not self.hw_bundle:
            raise ValueError("hw_bundle 与 app 必须引用同一套装配")
        cycle_token = object()
        uart3 = self.hw_bundle["uart"]["uart3"]

        # 高频跟随链路只消费当前拍里最新完整命令, 避免旧包排队拖慢控制闭环
        reader = getattr(uart3, "read_latest_line", None)
        if reader is not None:
            line = reader()
        else:
            line = uart3.read_line()
        if line:
            reply = self.app.handle_line(line, now_ms=now_ms, cycle_token=cycle_token)
            if reply:
                uart3.write_line(reply)

        # 再执行周期推进, 把超时和最小状态回包统一收口到同一轮末尾
        tick_reply = self.app.tick(now_ms=now_ms, cycle_token=cycle_token)
        if tick_reply:
            uart3.write_line(tick_reply)
        return tick_reply


class AssistantApp:
    """负责串联协议解析和执行运行时

    @brief 对外提供辅车命令处理和周期推进入口, 长期状态通过过程式运行时入口装配
    """

    def __init__(self, timeout_ms=None, hw_bundle=None):
        if timeout_ms is None:
            timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
        self.runtime_state = create_runtime_state(
            timeout_ms=timeout_ms,
            hw_bundle=hw_bundle,
        )
        self._timeout_reported = False

    def _render_ack(self):
        """生成对外确认回包

        @brief 辅助入口统一返回带最近序号的确认文本
        @return str
        """

        return "ACK,last_seq=%d" % int(self.runtime_state.last_seq)

    def _render_timeout(self):
        """生成对外超时回包

        @brief 周期检查发现跟随链路超时时明确对外报告
        @return str
        """

        return "TIMEOUT,last_seq=%d" % int(self.runtime_state.last_seq)

    def handle_line(self, line, now_ms, cycle_token=None):
        """处理一条主车输入

        @brief 解析文本协议并交给运行时执行
        @param line 原始命令文本
        @param now_ms 当前毫秒时间
        @return str
        """

        # 先把文本协议收口成结构化命令, 非法输入统一直接报错
        try:
            command = parse_command(line)
        except (TypeError, ValueError) as error:
            return _render_error_reply_with_raw(
                _normalize_error_reason(error),
                line,
            )

        # 命令合法后交给运行时执行, 由运行时决定状态变化和底座动作
        reply = apply_runtime_command(
            self.runtime_state,
            command,
            now_ms=now_ms,
            cycle_token=cycle_token,
        )

        if not bool(self.runtime_state.timeout):
            self._timeout_reported = False

        # 最后按协议类型挑选回包策略, 跟随报文本身不占用串口回包带宽
        if command.kind == "state_query":
            return str(reply)
        if str(reply) == "ERR":
            reason = (
                str(getattr(self.runtime_state, "last_error", "")).strip() or "unknown"
            )
            return _render_error_reply_with_raw(reason, line)
        if command.kind == "follow" or command.kind == "follow_velocity":
            return _render_follow_reply(command)
        return self._render_ack()

    def tick(self, now_ms, cycle_token=None):
        """推进辅车应用循环

        @brief 触发周期性安全检查和状态推进
        @param now_ms 当前毫秒时间
        @return str
        """

        reply = run_base_cycle(
            self.runtime_state,
            now_ms=now_ms,
            cycle_token=cycle_token,
            hw_bundle=self.runtime_state.hw_bundle,
        )
        if not bool(self.runtime_state.timeout):
            self._timeout_reported = False
            return ""
        if str(reply) == "DONE" and bool(self.runtime_state.timeout):
            self._timeout_reported = True
        return ""
