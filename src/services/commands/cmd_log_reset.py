"""log_reset 运行时日志配置复位指令处理器."""

from typing import cast

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_reset")
def handle(ctx: object, value: CommandValue) -> None:
    """恢复日志默认配置."""
    del value
    local_ctx = cast(LogCommandContext, ctx)
    local_ctx.logger_manager.reset_defaults()
