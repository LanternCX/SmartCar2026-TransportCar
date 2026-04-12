"""y 绝对位置指令处理器."""

from services.commanding.router import router


@router.command("y")
def handle(ctx, value):
    """设置世界系 Y 目标并退出 Y 速度模式."""
    if ctx.session.command_lock:
        return
    ctx.session.last_cmd["y"] = value
    ctx.session.last_cmd.pop("vy", None)
