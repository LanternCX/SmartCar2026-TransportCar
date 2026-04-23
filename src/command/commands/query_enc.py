"""
@file query_enc.py
@brief ?enc 查询处理器, 回传编码器观测快照摘要
"""

from command.router import router
from core.diagnostics import format_query_response


@router.query("enc")
def handle(ctx):
    """
    @brief 查询编码器当前原始数据, 通过序列化格式回复主控

    @details
    调用 ctx.build_encoder_snapshot() 采集当前时刻所有编码器的原始计数值与
    增量, 然后由 format_query_response() 将其序列化为结构化格式, 通过查询
    专用串口回复.该查询用于诊断编码器硬件连接与计数逻辑的完整性

    @param ctx TransportCar 实例, 需具备 build_encoder_snapshot() 和 get_query_uart()

    @dependencies format_query_response: 将数据字典序列化为回复格式
    """
    ctx.get_query_uart().write(
        format_query_response("enc", ctx.build_encoder_snapshot())
    )
