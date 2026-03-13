"""motor 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("motor")
def handle(ctx):
    """返回电机摘要."""
    ctx.reply(build_query_response_from_facade("motor", ctx.get_diagnostics_facade()))
