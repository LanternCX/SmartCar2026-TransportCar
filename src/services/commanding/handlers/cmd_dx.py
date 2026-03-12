"""dx 相对位移指令处理器."""

from services.commanding.router import router


@router.command("dx")
def handle(ctx, value):
    """暂存车体系 X 方向相对位移."""
    if ctx.session.command_lock:
        return
    ctx.session.pending_dx = value
