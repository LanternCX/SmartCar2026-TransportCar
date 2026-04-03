"""Stage 2 full 路径板端跟踪探针."""

import gc
import sys


RUNTIME_ROOTS = (
    "config",
    "control",
    "filters",
    "hardware",
    "services",
    "storage",
    "utils",
)

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


def _normalize_reason(exc):
    """归一化异常文本, 便于串口输出."""
    return str(exc).replace("\r", " ").replace("\n", " ").replace(",", ";")


def _clear_runtime_modules():
    """清理运行时相关模块, 避免半初始化残留."""
    for name in tuple(sys.modules):
        for root in RUNTIME_ROOTS:
            if name == root or name.startswith(root + "."):
                del sys.modules[name]
                break


def _print_mem(tag):
    """打印当前空闲内存."""
    gc.collect()
    mem_free = getattr(gc, "mem_free", None)
    free_bytes = -1
    if callable(mem_free):
        value = mem_free()
        if isinstance(value, bool):
            free_bytes = int(value)
        elif isinstance(value, int):
            free_bytes = value
        elif isinstance(value, float):
            free_bytes = int(value)
        elif isinstance(value, str):
            free_bytes = int(value)
    print("TRACE %s mem_free=%d" % (tag, free_bytes))


def _print_exception(stage, exc):
    """打印阶段失败信息和异常堆栈."""
    print(
        "TRACE stage=%s status=fail type=%s reason=%s"
        % (stage, type(exc).__name__, _normalize_reason(exc))
    )
    printer = getattr(sys, "print_exception", None)
    if printer is not None:
        printer(exc)


def main():
    """执行 full 路径逐阶段跟踪."""
    car = None
    _print_mem("start")
    _clear_runtime_modules()
    _print_mem("after_clear")

    try:
        from services.commanding.router import router

        _print_mem("after_import_router")
        from services.car import TransportCar

        _print_mem("after_import_transport_car")
        car = TransportCar(diagnostic_mode=True, vehicle_role="main")
        _print_mem("after_core_init")

        motion_runtime = getattr(car, "motion_runtime", None)
        vision_runtime = getattr(car, "vision_runtime_service", None)
        command_runtime = getattr(car, "command_runtime", None)
        if (
            motion_runtime is not None
            or vision_runtime is not None
            or command_runtime is not None
        ):
            _print_mem("after_feature_init")
        else:
            _print_mem("after_feature_init")

        ensure_query_handlers = getattr(car, "_ensure_query_handlers", None)
        if ensure_query_handlers is not None:
            ensure_query_handlers()
        print("TRACE registered_queries=%d" % len(router.registered_query_tokens()))
        _print_mem("after_ensure_handlers")

        car.pit_flag = True
        step_ok = 1 if car.step() else 0
        print("TRACE step_ok=%d tick_count=%d" % (step_ok, int(car.tick_count)))
        _print_mem("after_step")
        _print_mem("runtime_idle")

        facade = car.get_diagnostics_facade()
        print("TRACE health=%s" % facade.build_health_query_response().strip())
        print("TRACE vision=%s" % facade.build_vision_query_response().strip())
        _print_mem("after_queries")
        print("TRACE stage=done status=ok")
    except Exception as exc:
        _print_exception("full_trace", exc)
        _print_mem("after_fail")
    finally:
        if car is not None:
            ticker = getattr(car, "ticker", None)
            if ticker is not None:
                try:
                    ticker.stop()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
