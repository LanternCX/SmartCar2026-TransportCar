"""
@file query_lock.py
@brief ?lock 查询处理器, 回传当前运动锁定状态
"""

from command.router import router


@router.query("lock")
def handle(ctx):
    """
    @brief 查询当前运动锁定状态, 通过串口回复数值指示

    @details
    从 ctx.command_lock 读取当前是否处于锁定模式, 按格式回复主控: "?lock=0"
    表示解锁(允许运动指令执行), "?lock=1" 表示已锁定(忽略新运动指令)
    该查询不产生任何副作用, 是纯读操作, 常用于确认锁定命令的执行结果

    @param ctx TransportCar 实例, 需具备 command_lock 和 get_query_uart()

    @response_format "?lock=<0|1>\\r\\n"
    - 0: 运动解锁状态, 接受新指令
    - 1: 运动锁定状态, 忽略新指令
    """
    ctx.get_query_uart().write("?lock=%d\r\n" % (1 if ctx.command_lock else 0))
