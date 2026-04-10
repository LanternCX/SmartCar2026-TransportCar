"""?pos 查询处理器:返回当前里程计位置与航向角."""

from services.command_router import router


@router.query("pos")
def handle(ctx):
    """
    通过当前查询响应串口回传当前位置和航向角,格式:``?pos=x,y,yaw``.

    参数:
        ctx: TransportCar 实例.
    """
    ctx.get_query_uart().write(
        "?pos=%.3f,%.3f,%.2f\r\n" % (ctx.odometry.x, ctx.odometry.y, ctx.heading_est)
    )
