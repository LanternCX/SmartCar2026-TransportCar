"""log_reset 日志复位指令处理器."""

from services.commanding.router import router


@router.command("log_reset")
def handle(ctx, value):
    """恢复日志默认配置."""
    del value
    ctx.logger_manager.reset_defaults()
