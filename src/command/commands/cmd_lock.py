"""lock 整包锁定语义指令处理器."""

from command.router import router


@router.command("lock")
def handle(ctx, value):
    """记录当前整包是否要求进入锁定模式."""
    ctx._pending_lock = value != 0
