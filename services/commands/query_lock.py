"""?lock 查询处理器：返回当前运动锁定状态。"""
from services.command_router import router


@router.query("lock")
def handle(ctx) -> None:
    """
    通过 uart6 回传当前锁定状态，格式：``?lock=0`` 或 ``?lock=1``。

    参数：
        ctx: TransportCar 实例。
    """
    ctx.uart6.write("?lock=%d\r\n" % (1 if ctx.command_lock else 0))
