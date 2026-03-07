"""?tick 查询处理器:返回控制周期统计摘要."""

from services.command_router import router
from services.diagnostics import format_query_response


@router.query("tick")
def handle(ctx):
    """通过 uart6 回传控制周期统计信息."""
    ctx.uart6.write(format_query_response("tick", ctx.build_tick_snapshot()))
