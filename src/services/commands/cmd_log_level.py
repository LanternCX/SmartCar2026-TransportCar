"""log_level 运行时日志等级指令处理器."""

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_level", value_type="raw")
def handle(ctx: LogCommandContext, value: CommandValue) -> None:
    """更新日志等级."""
    ctx.logger_manager.set_level_name(str(value))
