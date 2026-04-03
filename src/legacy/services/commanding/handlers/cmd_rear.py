"""rear 后轮模式指令处理器."""

from services.commanding.router import router


@router.command("rear")
def handle(ctx, value):
    """切换后轮模式并输出调试提示."""
    if ctx.session.command_lock:
        return
    ctx.session.set_rear_mode(value != 0)
    ctx.uart3.write("Rear Only Mode: %s\r\n" % str(ctx.session.rear_only_mode))
