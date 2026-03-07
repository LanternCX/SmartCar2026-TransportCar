"""Stage 2 仅连接设备的安全探针脚本."""

import gc
import sys


REQUIRED_QUERY_TOKENS = (
    "health",
    "tick",
    "imu",
    "enc",
    "motor",
    "vision",
)


RELOAD_MODULES = (
    "config.params",
    "services.transport_car",
    "services.vision_protocol",
    "services.vision_state_machine",
    "services.diagnostics",
    "services.commands",
)


def _format_snapshot(prefix, snapshot):
    """将快照格式化为单行文本."""
    parts = []
    for key, value in snapshot.items():
        parts.append("%s=%s" % (key, value))
    return "%s %s" % (prefix, " ".join(parts))


def _stop_motors(car):
    """保险起见清零电机输出."""
    for state in getattr(car, "wheel_states", ()):  # pragma: no branch
        motor = state.get("motor")
        if motor is not None:
            motor.duty(0)


def _clear_stale_modules():
    """只清理本次调试涉及的最小模块集合."""
    module_names = tuple(sys.modules.keys())
    for module_name in module_names:
        if module_name in RELOAD_MODULES or module_name.startswith(
            "services.commands.query_"
        ):
            del sys.modules[module_name]


def main():
    """执行 Stage 2 安全探针."""
    car = None
    try:
        gc.collect()
        _clear_stale_modules()

        from services.transport_car import TransportCar

        car = TransportCar(diagnostic_mode=True)
        registered_queries = sorted(car._router._query_handlers.keys())
        missing = [
            token for token in REQUIRED_QUERY_TOKENS if token not in registered_queries
        ]

        print("STAGE2 status=ok")
        print(_format_snapshot("STAGE2 health", car.build_health_snapshot()))
        print(_format_snapshot("STAGE2 tick", car.build_tick_snapshot()))
        print(
            "STAGE2 queries count=%d missing=%s"
            % (len(registered_queries), "none" if not missing else ";".join(missing))
        )
    except Exception as exc:
        reason = str(exc).replace("\r", " ").replace("\n", " ").replace(",", ";")
        print("STAGE2 status=fail reason=%s" % reason)
        print_exception = getattr(sys, "print_exception", None)
        if print_exception is not None:
            print_exception(exc)
    finally:
        if car is not None:
            _stop_motors(car)


if __name__ == "__main__":
    main()
