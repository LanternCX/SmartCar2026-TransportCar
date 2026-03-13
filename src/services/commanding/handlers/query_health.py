"""health 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("health")
def handle(ctx):
    """返回健康诊断摘要."""
    ctx.reply(build_query_response_from_facade("health", ctx.get_diagnostics_facade()))
