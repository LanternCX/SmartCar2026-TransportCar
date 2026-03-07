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
    "services.command_router",
    "services.diagnostics",
    "services.vision_protocol",
    "services.vision_state_machine",
    "services.commands",
)


def _clear_stale_modules():
    """只清理 Stage 2 smoke 直接依赖的模块."""
    module_names = tuple(sys.modules.keys())
    for module_name in module_names:
        if module_name in RELOAD_MODULES or module_name.startswith(
            "services.commands.query_"
        ):
            del sys.modules[module_name]


def _check_transport_car_source():
    """轻量检查 transport_car.py 关键入口是否存在."""
    has_class = False
    has_diag_mode = False
    with open("services/transport_car.py", "r") as fp:
        for line in fp:
            if "class TransportCar" in line:
                has_class = True
            if "diagnostic_mode" in line:
                has_diag_mode = True
            if has_class and has_diag_mode:
                break
    return has_class, has_diag_mode


def main():
    """执行 Stage 2 安全探针."""
    try:
        gc.collect()
        _clear_stale_modules()

        from services.command_router import router
        from services import diagnostics  # noqa: F401
        from services import vision_protocol  # noqa: F401
        from services import vision_state_machine  # noqa: F401
        from services.commands import query_enc  # noqa: F401
        from services.commands import query_health  # noqa: F401
        from services.commands import query_imu  # noqa: F401
        from services.commands import query_motor  # noqa: F401
        from services.commands import query_tick  # noqa: F401
        from services.commands import query_vision  # noqa: F401

        registered_queries = sorted(router._query_handlers.keys())
        missing = [
            token for token in REQUIRED_QUERY_TOKENS if token not in registered_queries
        ]
        has_class, has_diag_mode = _check_transport_car_source()

        print("STAGE2 status=ok")
        print(
            "STAGE2 queries count=%d missing=%s"
            % (len(registered_queries), "none" if not missing else ";".join(missing))
        )
        print(
            "STAGE2 transport_source class=%d diagnostic_mode=%d"
            % (1 if has_class else 0, 1 if has_diag_mode else 0)
        )
    except Exception as exc:
        reason = str(exc).replace("\r", " ").replace("\n", " ").replace(",", ";")
        print("STAGE2 status=fail reason=%s" % reason)
        print_exception = getattr(sys, "print_exception", None)
        if print_exception is not None:
            print_exception(exc)


if __name__ == "__main__":
    main()
