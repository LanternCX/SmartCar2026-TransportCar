"""log_filter 日志过滤模式指令处理器."""

from services.commanding.router import router


@router.command("log_filter", value_type="raw")
def handle(ctx, value):
    """更新日志过滤模式."""
    ctx.logger_manager.set_filter_mode(str(value))
