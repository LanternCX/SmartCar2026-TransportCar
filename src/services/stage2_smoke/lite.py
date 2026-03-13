"""Stage 2 lite 模式 helper."""

from control.chassis_state import ChassisState
from services.commanding.session import CommandSession
from services.runtime.diagnostics_facade import DiagnosticsFacade
from services.stage2_smoke.shared import CaptureUart, probe_queries


class LiteContext:
    """lite 模式下的最小查询上下文."""

    def __init__(self):
        self.uart3 = CaptureUart()
        self.uart6 = CaptureUart()
        self.reply_uart = self.uart3
        self.command_session = CommandSession()
        self.chassis_state = ChassisState(
            heading_est=0.0,
            odometry=type("_LiteOdometry", (), {"x": 0.0, "y": 0.0})(),
            imu_data=[0.0] * 6,
            wheel_states=[],
            target_speeds={},
        )
        self.boot_time_ms = 0
        self.tick_count = 0
        self.last_loop_dt_us = 0
        self.max_loop_dt_us = 0
        self.loop_dt_total_us = 0
        self.loop_overrun_count = 0
        self.last_exception_text = "none"
        self.logger_manager = type(
            "_LiteLoggerManager",
            (),
            {
                "filter_modules": [],
                "profile_name": "RUN",
                "level_name": "INFO",
                "filter_mode": "off",
                "color_enabled": False,
            },
        )()
        self.vision_coordinator = type(
            "_LiteVisionCoordinator",
            (),
            {
                "resolved_target": None,
                "build_snapshot": lambda _self, _now_ms: {
                    "state": "lite",
                    "fresh": 0,
                },
            },
        )()
        self._diagnostics_facade = None

    def now_ms(self):
        return 0

    def get_query_uart(self):
        return getattr(self, "reply_uart", self.uart6)

    def reply(self, text):
        self.get_query_uart().write(text)

    def get_diagnostics_facade(self):
        facade = self._diagnostics_facade
        if facade is None:
            facade = DiagnosticsFacade(self)
            self._diagnostics_facade = facade
        return facade


def _registered_query_tokens(router):
    """返回已注册 query token, 兼容旧 router 形态."""
    getter = getattr(router, "registered_query_tokens", None)
    if getter is not None:
        return getter()
    handlers = getattr(router, "_query_handlers", {})
    return tuple(sorted(handlers))


def check_transport_source():
    """用行为探针验证显式 query 上下文协议."""
    from services.commanding.context import TransportCommandContext
    from services.commanding.session import CommandSession
    from services.runtime.uart_ingress import UartIngressService

    class _ProbeRuntime:
        def __init__(self):
            self.command_session = CommandSession()
            self.uart3 = CaptureUart()
            self.uart6 = CaptureUart()
            self.logger_manager = None
            self.chassis_state = ChassisState(
                odometry=type("_ProbeOdometry", (), {"x": 0.0, "y": 0.0})()
            )

    class _ProbeRouter:
        def __init__(self):
            self.calls = []

        def handle_query(self, token, ctx):
            self.calls.append((token, ctx.source, ctx.reply_uart))
            ctx.reply("?%s=%s\r\n" % (token, ctx.source))
            return True

    class _ProbeVisionCoordinator:
        def consume_uart_line(self, _line, _source, _now_ms):
            return False

    runtime = _ProbeRuntime()
    router = _ProbeRouter()
    service = UartIngressService(
        router=router,
        vision_coordinator=_ProbeVisionCoordinator(),
        build_context=lambda source: TransportCommandContext(
            runtime, reply_uart=getattr(runtime, source), source=source
        ),
        apply_command=lambda _line, source="uart6": None,
        command_log=lambda _line: None,
        emit_error=lambda _message: None,
        now_ms=lambda: 0,
    )
    service.handle_line("?probe", "uart3")
    service.handle_line("?probe", "uart6")
    transport_source_ok = router.calls == [
        ("probe", "uart3", runtime.uart3),
        ("probe", "uart6", runtime.uart6),
    ]
    query_uart_ok = runtime.uart3.messages == [
        "?probe=uart3\r\n"
    ] and runtime.uart6.messages == ["?probe=uart6\r\n"]
    return transport_source_ok, query_uart_ok


def collect_lite_transport_summary(tokens, check_transport_source_func):
    """执行 lite 模式下的最小可信查询 smoke."""
    from services.commanding.router import router
    import services.commanding.handlers as _commanding_handlers

    _commanding_handlers.load_query_handlers()

    registered = _registered_query_tokens(router)
    missing = [name for name in tokens if name not in registered]
    transport_source_ok, query_uart_ok = check_transport_source_func()
    ctx = LiteContext()
    query_ok, query_outputs = probe_queries(
        tokens, lambda name: router.handle_query(name, ctx), ctx.uart3
    )

    status = "ok"
    reason = "ok"
    if missing:
        status = "fail"
        reason = "missing queries: %s" % ";".join(missing)
    elif not transport_source_ok:
        status = "fail"
        reason = "transport query source marker missing"
    elif not query_uart_ok:
        status = "fail"
        reason = "transport query uart marker missing"
    elif not query_ok:
        status = "fail"
        reason = "query chain failed"

    return {
        "status": status,
        "reason": reason,
        "transport_mode": "lite",
        "init_ok": 0,
        "query_count": len(registered),
        "missing_queries": missing,
        "query_ok": query_ok,
        "query_outputs": query_outputs,
        "step_ok": 0,
        "tick_count": 0,
        "snapshots": {},
        "transport_source_ok": 1 if transport_source_ok else 0,
        "query_uart_ok": 1 if query_uart_ok else 0,
    }


def main():
    """打印 lite 模式 Stage 2 smoke 结果."""
    tokens = (
        "health",
        "tick",
        "imu",
        "enc",
        "motor",
        "vision",
        "pos",
        "lock",
        "log",
    )
    summary = collect_lite_transport_summary(tokens, check_transport_source)
    if summary["status"] != "ok":
        print("STAGE2 status=fail reason=%s" % summary["reason"])
    else:
        print("STAGE2 status=ok")
    print(
        "STAGE2 queries count=%d missing=%s"
        % (
            int(summary["query_count"]),
            "none"
            if not summary["missing_queries"]
            else ";".join(summary["missing_queries"]),
        )
    )
    print(
        "STAGE2 smoke mode=lite init=0 queries=%d step=0 tick_count=0 snapshots=none"
        % int(summary["query_ok"])
    )
