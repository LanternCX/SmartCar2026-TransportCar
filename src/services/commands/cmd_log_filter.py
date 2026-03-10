"""log_filter 运行时日志过滤模式指令处理器."""

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_filter", value_type="raw")
def handle(ctx: LogCommandContext, value: CommandValue) -> None:
    """更新日志模块过滤模式."""
    ctx.logger_manager.set_filter_mode(str(value))
