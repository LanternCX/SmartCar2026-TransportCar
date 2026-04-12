"""log_profile 日志档位指令处理器."""

from services.commanding.router import router


@router.command("log_profile", value_type="raw")
def handle(ctx, value):
    """更新日志预设档位."""
    ctx.logger_manager.set_profile(str(value))
