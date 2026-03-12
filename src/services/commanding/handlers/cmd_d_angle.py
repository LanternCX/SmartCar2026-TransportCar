"""d_angle 相对角度指令处理器."""

from services.commanding.router import router


@router.command("d_angle", "dyaw", "da")
def handle(ctx, value):
    """暂存相对偏航角增量."""
    if ctx.session.command_lock:
        return
    ctx.session.pending_d_angle = value
