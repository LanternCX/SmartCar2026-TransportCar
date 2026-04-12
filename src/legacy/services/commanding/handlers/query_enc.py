"""enc 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("enc")
def handle(ctx):
    """返回编码器摘要."""
    ctx.reply(build_query_response_from_facade("enc", ctx.get_diagnostics_facade()))
