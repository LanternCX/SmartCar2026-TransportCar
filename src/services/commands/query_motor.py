"""?motor 查询处理器:返回电机目标与占空比摘要."""

from services.command_router import router
from services.diagnostics import format_query_response


@router.query("motor")
def handle(ctx):
    """通过当前查询响应串口回传电机诊断信息."""
    ctx.get_query_uart().write(
        format_query_response("motor", ctx.build_motor_snapshot())
    )
