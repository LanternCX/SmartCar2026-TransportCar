"""?lock 查询处理器:返回当前运动锁定状态."""

from command.router import router


@router.query("lock")
def handle(ctx):
    """
    通过当前查询响应串口回传当前锁定状态,格式:``?lock=0`` 或 ``?lock=1``.

    参数:
        ctx: TransportCar 实例.
    """
    ctx.get_query_uart().write("?lock=%d\r\n" % (1 if ctx.command_lock else 0))
