"""?tick 查询处理器:返回控制周期统计摘要."""

from services.command_router import router
from services.diagnostics import format_query_response


@router.query("tick")
def handle(ctx):
    """通过当前查询响应串口回传控制周期统计信息."""
    ctx.get_query_uart().write(format_query_response("tick", ctx.build_tick_snapshot()))
