"""
@file query_imu.py
@brief ?imu 查询处理器, 回传 IMU 姿态与角速度快照
"""

from command.router import router
from core.diagnostics import format_query_response


@router.query("imu")
def handle(ctx):
    """
    @brief 查询 IMU 当前姿态与角速度, 通过序列化格式回复主控

    @details
    调用 ctx.build_imu_snapshot() 采集当前时刻的 IMU 观测数据, 包括欧拉角、
    四元数、角速度等姿态信息, 然后由 format_query_response() 将其序列化为
    结构化格式, 通过查询专用串口回复.该查询用于诊断 IMU 与姿态估计的准确性

    @param ctx TransportCar 实例, 需具备 build_imu_snapshot() 和 get_query_uart()

    @dependencies format_query_response: 将数据字典序列化为回复格式
    """
    ctx.get_query_uart().write(format_query_response("imu", ctx.build_imu_snapshot()))
