"""log_filter 运行时日志过滤模式指令处理器."""

from typing import cast

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_filter", value_type="raw")
def handle(ctx: object, value: CommandValue) -> None:
    """更新日志模块过滤模式."""
    local_ctx = cast(LogCommandContext, ctx)
    local_ctx.logger_manager.set_filter_mode(str(value))
