"""@brief 搬运车兼容属性与命令接线 mixin.

@note
该模块负责两类兼容面:
1. 历史脚本和测试仍会访问的实例属性桥接
2. UART ingress 到 router 的统一接线
"""

from services.commanding.context import TransportCommandContext
from services.commanding.session import CommandSession
from services.runtime.uart_ingress import UartIngressService


class CompatMixin:
    """@brief 提供兼容属性与命令接线能力."""

    def _emit_error_log(self, message: str) -> None:
        """@brief 记录结构化错误日志并更新最近异常文本.

        @param message 原始错误文本
        """

        # 这里故意保持极简字符串格式, 避免旧 formatter 路径再次放大 OOM 风险
        text = str(message)
        self.last_exception_text = text
        self.error_count = int(getattr(self, "error_count", 0) or 0) + 1
        self.last_error_stage = "runtime"
        if getattr(self, "_last_error_log_text", None) == text:
            return
        self._last_error_log_text = text
        uart3 = getattr(self, "uart3", None)
        if uart3 is None:
            return
        try:
            uart3.write("ERRRAW %s\r\n" % text)
        except Exception:
            return

    def _record_oom(self, stage: str) -> None:
        """@brief 记录一次轻量 OOM 观测信号.

        @param stage OOM 发生阶段
        """
        runtime_core = getattr(self, "runtime_core", None)
        if runtime_core is not None:
            runtime_core.record_oom(stage)
            return
        self.oom_count = int(getattr(self, "oom_count", 0) or 0) + 1
        self.last_oom_stage = str(stage)

    def _log_uart_command(self, line: str) -> None:
        """@brief 记录接收到的 UART 原始命令.

        @param line 原始命令文本
        """
        self.log_command.info("RCV: %s" % line)

    @property
    def command_session(self):
        """@brief 返回命令会话 owner.

        @return `CommandSession`

        @note
        host 测试可能绕过 `__init__`, 因此这里保留按需补建兜底
        """
        session = getattr(self, "_command_session", None)
        if session is None:
            session = CommandSession()
            self._command_session = session
        return session

    @property
    def chassis_state(self):
        """@brief 返回底盘状态 owner.

        @return 当前 `chassis_state`
        """
        runtime = getattr(self, "motion_runtime", None)
        if runtime is None:
            return getattr(self, "_chassis_state", None)
        return getattr(runtime, "chassis_state", None)

    @chassis_state.setter
    def chassis_state(self, value):
        """@brief 更新底盘状态 owner.

        @param value 新的底盘状态对象
        """

        # 若 controller 已存在, 必须同步 state 指针, 否则会形成双份状态引用
        runtime = getattr(self, "motion_runtime", None)
        if runtime is None:
            self._chassis_state = value
        else:
            runtime.chassis_state = value
        controller = getattr(self, "chassis_controller", None)
        if controller is not None and hasattr(controller, "state"):
            controller.state = value

    @property
    def chassis_controller(self):
        """@brief 返回底盘控制器 owner.

        @return 当前 `chassis_controller`
        """
        runtime = getattr(self, "motion_runtime", None)
        if runtime is None:
            return getattr(self, "_chassis_controller", None)
        return getattr(runtime, "chassis_controller", None)

    @chassis_controller.setter
    def chassis_controller(self, value):
        """@brief 更新底盘控制器 owner.

        @param value 新的控制器对象
        """
        runtime = getattr(self, "motion_runtime", None)
        if runtime is None:
            self._chassis_controller = value
            return
        runtime.chassis_controller = value
        if value is not None and hasattr(value, "state"):
            runtime.chassis_state = value.state

    def __getattr__(self, name: str):
        """@brief 为少量历史属性提供只读兼容转发.

        @param name 属性名
        @return 对应 owner 上的属性值
        @warning 这里只允许兼容少量历史字段, 不能继续扩散成 God object 回潮
        """
        if name in ("imu", "motors", "encoders", "ident_lookup"):
            runtime = getattr(self, "motion_runtime", None)
            if runtime is not None and hasattr(runtime, name):
                return getattr(runtime, name)
        try:
            from services.car.core import _get_lazy_vision_attr

            return _get_lazy_vision_attr(self, name)
        except AttributeError:
            pass
        raise AttributeError(name)

    def _build_handler_context(self, source="uart6"):
        """@brief 构造单次路由调用所需的显式上下文.

        @param source 输入来源
        @return `TransportCommandContext`
        """
        reply_uart = getattr(self, source, None) or self.uart6
        return TransportCommandContext(self, reply_uart=reply_uart, source=source)

    def _handle_uart_line(self, line, source):
        """@brief 按来源处理单行串口输入.

        @param line 原始命令行
        @param source 串口来源
        """
        self._ensure_uart_ingress().handle_line(line, source)

    def handle_uart_line(self, line, source="uart6"):
        """@brief 公开单行串口入口.

        @param line 原始命令行
        @param source 串口来源
        """
        self._handle_uart_line(line, source)

    def get_query_uart(self):
        """@brief 返回查询响应应写入的串口.

        @return 当前 query 回复串口
        """
        return self.uart6

    def _process_uart(self):
        """@brief 轮询两个串口并处理输入.

        @note
        主循环每拍都经过这里, 所以逻辑保持最薄, 仅做 source 分发
        """
        self._poll_uart_source(self.uart3, "uart3")
        self._poll_uart_source(self.uart6, "uart6")

    def _poll_uart_source(self, uart, source):
        """@brief 轮询单个串口并按行转交 ingress.

        @param uart 串口对象
        @param source 串口来源
        """
        self._ensure_uart_ingress().poll_source(uart, source)

    def _ensure_uart_ingress(self):
        """@brief 返回 UART ingress 服务.

        @return `UartIngressService`

        @note
        首次缺失时按当前依赖懒构造; 视觉协调器通过 provider 后移到真正视觉流量时再解析
        """
        ingress = getattr(self, "uart_ingress", None)
        if ingress is None:
            trace_mem = self.__dict__.get("trace_runtime_mem")
            if trace_mem is None:
                trace_mem = getattr(type(self), "trace_runtime_mem", None)
            trace_fail = self.__dict__.get("trace_runtime_failure")
            if trace_fail is None:
                trace_fail = getattr(type(self), "trace_runtime_failure", None)
            uart = self.__dict__.get("uart3")
            if callable(trace_mem):
                trace_mem("before_uart_ingress_init", uart=uart)
            try:
                ingress = UartIngressService(
                    router=self._router,
                    ensure_query_handlers=self._ensure_query_handlers,
                    build_context=self._build_handler_context,
                    apply_command=self.apply_command,
                    command_log=self._log_uart_command,
                    emit_error=self._emit_error_log,
                    now_ms=self._now_ms,
                    get_vision_coordinator=self._ensure_vision_coordinator,
                )
                self.uart_ingress = ingress
                if callable(trace_mem):
                    trace_mem("after_uart_ingress_init", uart=uart)
            except Exception as exc:
                if callable(trace_fail):
                    trace_fail("uart_ingress_init", exc, uart=uart)
                raise
        return ingress

    def apply_command(self, line, source="uart6"):
        """@brief 分发原始命令行到 router.

        @param line 原始命令行
        @param source 串口来源
        """

        # command handler 必须在首次命令到来时显式激活, 不能退回 import-time 全量注册
        if not line:
            return
        runtime = getattr(self, "command_runtime", None)
        if runtime is not None:
            runtime.activate_full_commands()
            self._command_handlers_ready = bool(
                getattr(runtime, "command_handlers_ready", True)
            )
        else:
            self._ensure_command_handlers()
        self._router.route(line, self._build_handler_context(source=source))
