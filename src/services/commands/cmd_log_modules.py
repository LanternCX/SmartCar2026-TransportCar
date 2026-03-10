"""log_modules 运行时日志模块过滤列表指令处理器."""

from typing import cast

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_modules", value_type="raw")
def handle(ctx: object, value: CommandValue) -> None:
    """更新日志模块过滤列表."""
    local_ctx = cast(LogCommandContext, ctx)
    raw_value = str(value).strip()
    if raw_value.lower() == "none" or not raw_value:
        modules = ()
    else:
        modules = tuple(
            module_name.strip()
            for module_name in raw_value.split("|")
            if module_name.strip()
        )
    local_ctx.logger_manager.set_filter_modules(modules)
