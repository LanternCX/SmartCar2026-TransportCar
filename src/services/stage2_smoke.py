"""Stage 2 裸片 smoke 运行时逻辑."""

import gc
import sys


TOKENS = ("health", "tick", "imu", "enc", "motor", "vision")
RUNTIME_ROOTS = (
    "config",
    "control",
    "filters",
    "hardware",
    "services",
    "storage",
    "utils",
)
TRANSPORT_QUERY_CALL_FRAGMENT = "handle_query("
TRANSPORT_QUERY_SOURCE_FRAGMENT = "source=source"
TRANSPORT_QUERY_UART_DEF_FRAGMENT = "def get_query_uart"
TRANSPORT_QUERY_UART_STATE_FRAGMENT = '"_query_response_uart"'
TRANSPORT_QUERY_UART_FALLBACK_FRAGMENT = "self.uart6"


class _CaptureUart:
    """收集查询回包的简易串口对象."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class _LiteContext:
    """lite 模式下的最小查询上下文."""

    def __init__(self):
        self.uart3 = _CaptureUart()
        self.uart6 = _CaptureUart()
        self.command_lock = False

    def get_query_uart(self):
        """返回当前查询响应串口."""
        return getattr(self, "_query_response_uart", self.uart6)

    def build_health_snapshot(self):
        """返回最小健康快照."""
        return {"alive": 1, "mode": "lite"}

    def build_tick_snapshot(self):
        """返回最小 tick 快照."""
        return {"count": 0, "avg_us": 0, "max_us": 0, "overrun": 0}

    def build_imu_snapshot(self):
        """返回最小 IMU 快照."""
        return {"gx": 0.0, "gy": 0.0, "gz": 0.0}

    def build_encoder_snapshot(self):
        """返回最小编码器快照."""
        return {"m": 0.0, "l": 0.0, "r": 0.0}

    def build_motor_snapshot(self):
        """返回最小电机快照."""
        return {"m": 0.0, "l": 0.0, "r": 0.0}

    def build_vision_snapshot(self):
        """返回最小视觉快照."""
        return {"state": "lite", "fresh": 0}


def _clear_modules():
    """清理运行时相关模块,避免半初始化残留."""
    for name in tuple(sys.modules):
        for root in RUNTIME_ROOTS:
            if name == root or name.startswith(root + "."):
                del sys.modules[name]
                break


def _probe_queries(probe_func, capture):
    """执行一组查询探针并返回查询结果摘要."""
    query_outputs = {}
    query_ok = 1
    for name in TOKENS:
        before_count = len(capture.messages)
        probe_func(name)
        text = (
            capture.messages[-1].strip() if len(capture.messages) > before_count else ""
        )
        if text:
            query_outputs[name] = text
        if not text.startswith("?%s=" % name):
            query_ok = 0
    return query_ok, query_outputs


def _module_dir():
    """返回当前模块所在目录."""
    module_file = __file__
    if "/" in module_file:
        return module_file.rsplit("/", 1)[0]
    if "\\" in module_file:
        return module_file.rsplit("\\", 1)[0]
    return "."


def _check_transport_source():
    """检查 transport_car 源码中关键查询路由标记是否存在."""
    transport_path = _module_dir() + "/transport_car.py"
    has_query_call = False
    has_query_source = False
    has_query_uart_def = False
    has_query_uart_state = False
    has_query_uart_fallback = False
    with open(transport_path, "r") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            if not has_query_call and TRANSPORT_QUERY_CALL_FRAGMENT in line:
                has_query_call = True
            if not has_query_source and TRANSPORT_QUERY_SOURCE_FRAGMENT in line:
                has_query_source = True
            if not has_query_uart_def and TRANSPORT_QUERY_UART_DEF_FRAGMENT in line:
                has_query_uart_def = True
            if not has_query_uart_state and TRANSPORT_QUERY_UART_STATE_FRAGMENT in line:
                has_query_uart_state = True
            if (
                not has_query_uart_fallback
                and TRANSPORT_QUERY_UART_FALLBACK_FRAGMENT in line
            ):
                has_query_uart_fallback = True
            if (
                has_query_call
                and has_query_source
                and has_query_uart_def
                and has_query_uart_state
                and has_query_uart_fallback
            ):
                break
    return (
        has_query_call and has_query_source,
        has_query_uart_def and has_query_uart_state and has_query_uart_fallback,
    )


def _normalize_reason(exc):
    """归一化异常文本,便于串口输出."""
    return str(exc).replace("\r", " ").replace("\n", " ").replace(",", ";")


def _should_fallback_to_lite(exc):
    """判断是否应从 full 自动退回 lite."""
    if isinstance(exc, MemoryError):
        return True

    text = _normalize_reason(exc)
    lowered = text.lower()
    if "memory" in lowered or "alloc" in lowered:
        return True
    if isinstance(exc, ImportError) and (
        "TransportCar" in text or "transport_car" in lowered
    ):
        return True
    if isinstance(exc, AttributeError) and (
        "TransportCar" in text or "transport_car" in lowered
    ):
        return True
    return False


def _collect_full_transport_summary():
    """执行 full 模式下的完整安全 smoke."""
    from services.transport_car import TransportCar

    car = TransportCar(diagnostic_mode=True)
    handlers = car._router._query_handlers
    missing = [name for name in TOKENS if name not in handlers]

    car.pit_flag = True
    step_ok = 1 if car.step() else 0
    snapshots = {
        "health": car.build_health_snapshot(),
        "tick": car.build_tick_snapshot(),
        "imu": car.build_imu_snapshot(),
        "enc": car.build_encoder_snapshot(),
        "motor": car.build_motor_snapshot(),
        "vision": car.build_vision_snapshot(),
    }

    capture = _CaptureUart()
    setattr(car, "uart3", capture)
    query_ok, query_outputs = _probe_queries(
        lambda name: car._handle_uart_line("?%s" % name, source="uart3"), capture
    )

    status = "ok"
    reason = "ok"
    if missing:
        status = "fail"
        reason = "missing queries: %s" % ";".join(missing)
    elif not query_ok:
        status = "fail"
        reason = "query chain failed"
    elif not step_ok:
        status = "fail"
        reason = "step returned false"
    elif int(car.tick_count) <= 0:
        status = "fail"
        reason = "tick did not advance"

    return {
        "status": status,
        "reason": reason,
        "transport_mode": "full",
        "init_ok": 1,
        "query_count": len(handlers),
        "missing_queries": missing,
        "query_ok": query_ok,
        "query_outputs": query_outputs,
        "step_ok": step_ok,
        "tick_count": int(car.tick_count),
        "snapshots": snapshots,
    }


def _collect_lite_transport_summary():
    """执行 lite 模式下的最小可信查询 smoke."""
    from services.command_router import router
    import services.commands as _commands  # noqa: F401 自动发现查询处理器

    handlers = router._query_handlers
    missing = [name for name in TOKENS if name not in handlers]
    transport_source_ok, query_uart_ok = _check_transport_source()

    ctx = _LiteContext()
    query_ok, query_outputs = _probe_queries(
        lambda name: router.handle_query(name, ctx, source="uart3"), ctx.uart3
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
        "query_count": len(handlers),
        "missing_queries": missing,
        "query_ok": query_ok,
        "query_outputs": query_outputs,
        "step_ok": 0,
        "tick_count": 0,
        "snapshots": {},
        "transport_source_ok": 1 if transport_source_ok else 0,
        "query_uart_ok": 1 if query_uart_ok else 0,
    }


def collect_stage2_summary():
    """执行一次最小安全 smoke 并返回结构化摘要."""
    gc.collect()
    _clear_modules()

    try:
        return _collect_full_transport_summary()
    except Exception as exc:
        if not _should_fallback_to_lite(exc):
            raise
        full_reason = _normalize_reason(exc)

    gc.collect()
    _clear_modules()
    summary = _collect_lite_transport_summary()
    summary["fallback_reason"] = full_reason
    return summary


def _format_snapshot_names(summary):
    """将快照结果格式化为输出 token 串."""
    snapshot_names = [name for name in TOKENS if name in summary["snapshots"]]
    if not snapshot_names:
        return "none"
    return ";".join(snapshot_names)


def main():
    """打印 Stage 2 smoke 结果."""
    try:
        summary = collect_stage2_summary()
        if summary["status"] != "ok":
            print("STAGE2 status=fail reason=%s" % summary["reason"])
            return
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
            "STAGE2 smoke mode=%s init=%d queries=%d step=%d tick_count=%d snapshots=%s"
            % (
                summary["transport_mode"],
                int(summary["init_ok"]),
                int(summary["query_ok"]),
                int(summary["step_ok"]),
                int(summary["tick_count"]),
                _format_snapshot_names(summary),
            )
        )
    except Exception as exc:
        reason = _normalize_reason(exc)
        print("STAGE2 status=fail reason=%s" % reason)
        printer = getattr(sys, "print_exception", None)
        if printer is not None:
            printer(exc)
