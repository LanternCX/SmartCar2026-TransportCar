"""
@file query_pos.py
@brief ?pos 查询处理器, 回传当前位置与航向角快照
"""

from command.router import router


@router.query("pos")
def handle(ctx):
    """
    @brief 查询当前里程计位置与航向角, 通过串口回复格式化响应

    @details
    从 ctx.odometry 读取当前估计的世界系位置(x, y), 以及 ctx.heading_est 读取
    当前航向角, 按固定格式回复主控: "?pos=x, y, yaw\\r\\n".其中 x 与 y 精度到
    毫米(%.3f), 航向角精度到厘度(%.2f).查询不产生任何副作用, 是纯读操作

    @param ctx TransportCar 实例, 需具备 get_query_uart()、odometry、heading_est

    @response_format "?pos=%.3f, %.3f, %.2f\\r\\n"
    - x: 世界系 X 坐标(m)
    - y: 世界系 Y 坐标(m)
    - yaw: 航向角(度, 范围 -180~180)
    """
    ctx.get_query_uart().write(
        "?pos=%.3f,%.3f,%.2f\r\n" % (ctx.odometry.x, ctx.odometry.y, ctx.heading_est)
    )
