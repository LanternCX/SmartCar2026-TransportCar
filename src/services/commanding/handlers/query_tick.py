"""tick 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("tick")
def handle(ctx):
    """返回 tick 统计摘要."""
    ctx.reply(build_query_response_from_facade("tick", ctx.get_diagnostics_facade()))
