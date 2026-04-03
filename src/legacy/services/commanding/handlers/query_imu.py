"""imu 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("imu")
def handle(ctx):
    """返回 IMU 摘要."""
    ctx.reply(build_query_response_from_facade("imu", ctx.get_diagnostics_facade()))
