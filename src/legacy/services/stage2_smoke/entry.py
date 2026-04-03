"""Stage 2 裸片 smoke 入口与共享 helper."""

import gc
import sys


TOKENS = (
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
RUNTIME_ROOTS = (
    "config",
    "control",
    "filters",
    "hardware",
    "services",
    "storage",
    "utils",
)
PACKAGE_ROOT = "services.stage2_smoke"


def _clear_modules():
    """清理运行时相关模块, 避免半初始化残留."""
    for name in tuple(sys.modules):
        if name == PACKAGE_ROOT:
            continue
        for root in RUNTIME_ROOTS:
            if name == root or name.startswith(root + "."):
                del sys.modules[name]
                break


def _normalize_reason(exc):
    """归一化异常文本, 便于串口输出."""
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


def _format_snapshot_names(summary):
    """将快照结果格式化为输出 token 串."""
    package = _get_package_module()
    snapshot_names = [name for name in package.TOKENS if name in summary["snapshots"]]
    if not snapshot_names:
        return "none"
    return ";".join(snapshot_names)


def _get_package_module():
    """返回公共包模块, 让入口逻辑感知包级 monkeypatch."""
    return sys.modules["services.stage2_smoke"]


def _CaptureUart():
    """构造查询回包采集 UART."""
    __import__("services.stage2_smoke.full")
    module = sys.modules["services.stage2_smoke.full"]
    return module.CaptureUart()


def _LiteContext():
    """构造 lite 模式最小查询上下文."""
    __import__("services.stage2_smoke.lite")
    module = sys.modules["services.stage2_smoke.lite"]
    return module.LiteContext()


def _check_transport_source():
    """验证显式 query 上下文协议."""
    __import__("services.stage2_smoke.lite")
    module = sys.modules["services.stage2_smoke.lite"]
    return module.check_transport_source()


def _collect_full_transport_summary():
    """执行 full 模式下的完整安全 smoke."""
    __import__("services.stage2_smoke.full")
    module = sys.modules["services.stage2_smoke.full"]
    package = _get_package_module()
    return module.collect_full_transport_summary(package.TOKENS)


def _collect_lite_transport_summary():
    """执行 lite 模式下的最小可信查询 smoke."""
    __import__("services.stage2_smoke.lite")
    module = sys.modules["services.stage2_smoke.lite"]
    package = _get_package_module()
    return module.collect_lite_transport_summary(
        package.TOKENS, package._check_transport_source
    )


def collect_stage2_summary():
    """执行一次最小安全 smoke 并返回结构化摘要."""
    package = _get_package_module()

    gc.collect()
    package._clear_modules()

    try:
        return package._collect_full_transport_summary()
    except Exception as exc:
        if not _should_fallback_to_lite(exc):
            raise
        full_reason = _normalize_reason(exc)

    gc.collect()
    package._clear_modules()
    summary = package._collect_lite_transport_summary()
    summary["fallback_reason"] = full_reason
    return summary


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
