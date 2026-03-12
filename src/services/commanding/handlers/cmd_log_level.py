"""log_level 日志等级指令处理器."""

from services.commanding.router import router


@router.command("log_level", value_type="raw")
def handle(ctx, value):
    """更新日志等级."""
    ctx.logger_manager.set_level_name(str(value))
