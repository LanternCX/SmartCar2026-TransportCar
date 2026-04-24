"""
@file query_health.py
@brief ?health 查询处理器, 回传系统运行期健康指标快照
"""

from command.router import router
from core.diagnostics import format_query_response


@router.query("health")
def handle(ctx):
    """
    @brief 查询系统当前健康状态, 通过序列化格式回复主控

    @details
    调用 ctx.build_health_snapshot() 采集当前时刻的系统级诊断指标, 包括
    资源占用、通信延迟、错误率等运行期指标, 然后由 format_query_response()
    将其序列化为结构化格式, 通过查询专用串口回复.该查询用于长期运行监控
    与故障预警

    @param ctx TransportCar 实例, 需具备 build_health_snapshot() 和 get_query_uart()

    @dependencies format_query_response: 将数据字典序列化为回复格式
    """
    ctx.get_query_uart().write(
        format_query_response("health", ctx.build_health_snapshot())
    )
