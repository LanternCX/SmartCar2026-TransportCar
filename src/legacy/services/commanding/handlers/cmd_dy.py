"""dy 相对位移指令处理器."""

from services.commanding.router import router


@router.command("dy")
def handle(ctx, value):
    """暂存车体系 Y 方向相对位移."""
    if ctx.session.command_lock:
        return
    ctx.session.pending_dy = value
