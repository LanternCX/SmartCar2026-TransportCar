"""angle 绝对角度指令处理器."""

from services.commanding.router import router


@router.command("angle", "yaw")
def handle(ctx, value):
    """设置绝对偏航角目标."""
    if ctx.session.command_lock:
        return
    ctx.session.last_cmd["angle"] = value
