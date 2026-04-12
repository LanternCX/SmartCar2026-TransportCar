"""log_modules 日志模块列表指令处理器."""

from services.commanding.router import router


@router.command("log_modules", value_type="raw")
def handle(ctx, value):
    """更新日志过滤模块列表."""
    raw_value = str(value).strip()
    if raw_value.lower() == "none" or not raw_value:
        modules = ()
    else:
        modules = tuple(
            module_name.strip()
            for module_name in raw_value.split("|")
            if module_name.strip()
        )
    ctx.logger_manager.set_filter_modules(modules)
