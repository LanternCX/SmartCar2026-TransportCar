"""
@file query_tick.py
@brief ?tick 查询处理器, 回传控制周期统计快照
"""

from command.router import router
from core.diagnostics import format_query_response


@router.query("tick")
def handle(ctx):
    """
    @brief 查询控制周期统计信息, 通过序列化格式回复主控

    @details
    调用 ctx.build_tick_snapshot() 采集当前时刻的控制周期相关统计数据, 包括
    周期时间、帧率、丢帧率等性能指标, 然后由 format_query_response() 将其序列化
    为结构化格式, 通过查询专用串口回复.该查询用于诊断控制层的实时性性能

    @param ctx TransportCar 实例, 需具备 build_tick_snapshot() 和 get_query_uart()

    @dependencies format_query_response: 将数据字典序列化为回复格式
    """
    ctx.get_query_uart().write(format_query_response("tick", ctx.build_tick_snapshot()))
