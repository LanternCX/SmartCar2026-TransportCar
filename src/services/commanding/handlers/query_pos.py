"""pos 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("pos")
def handle(ctx):
    """返回当前位置与航向角."""
    ctx.reply(build_query_response_from_facade("pos", ctx.get_diagnostics_facade()))
