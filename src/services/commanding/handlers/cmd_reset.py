"""reset 全量复位指令处理器."""

from services.commanding.router import router


@router.command("reset")
def handle(ctx, value):
    """复位运行时与命令会话状态."""
    del value
    ctx.reset_runtime()
