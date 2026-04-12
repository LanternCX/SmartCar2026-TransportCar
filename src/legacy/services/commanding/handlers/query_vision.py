"""vision 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("vision")
def handle(ctx):
    """返回视觉摘要."""
    ctx.reply(build_query_response_from_facade("vision", ctx.get_diagnostics_facade()))
