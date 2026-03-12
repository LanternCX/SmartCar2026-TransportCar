"""x 绝对位置指令处理器."""

from services.commanding.router import router


@router.command("x")
def handle(ctx, value):
    """设置世界系 X 目标并退出 X 速度模式."""
    if ctx.session.command_lock:
        return
    ctx.session.last_cmd["x"] = value
    ctx.session.last_cmd.pop("vx", None)
