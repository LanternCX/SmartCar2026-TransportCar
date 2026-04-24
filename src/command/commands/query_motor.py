"""
@file query_motor.py
@brief ?motor 查询处理器, 回传电机控制状态快照摘要
"""

from command.router import router
from core.diagnostics import format_query_response


@router.query("motor")
def handle(ctx):
    """
    @brief 查询电机当前目标与占空比, 通过序列化格式回复主控

    @details
    调用 ctx.build_motor_snapshot() 采集当前时刻所有电机的目标速度、实际占空比
    与运转方向, 然后由 format_query_response() 将其序列化为结构化格式, 通过查询
    专用串口回复.该查询用于诊断电机驱动层的输出是否与指令对应

    @param ctx TransportCar 实例, 需具备 build_motor_snapshot() 和 get_query_uart()

    @dependencies format_query_response: 将数据字典序列化为回复格式
    """
    ctx.get_query_uart().write(
        format_query_response("motor", ctx.build_motor_snapshot())
    )
