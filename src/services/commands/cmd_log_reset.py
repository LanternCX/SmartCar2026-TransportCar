"""log_reset 运行时日志配置复位指令处理器."""

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_reset")
def handle(ctx: LogCommandContext, value: CommandValue) -> None:
    """恢复日志默认配置."""
    del value
    ctx.logger_manager.reset_defaults()
