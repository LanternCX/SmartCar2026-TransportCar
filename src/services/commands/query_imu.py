"""?imu 查询处理器:返回姿态与角速度摘要."""

from services.command_router import router
from services.diagnostics import format_query_response


@router.query("imu")
def handle(ctx):
    """通过当前查询响应串口回传 IMU 诊断信息."""
    ctx.get_query_uart().write(format_query_response("imu", ctx.build_imu_snapshot()))
