"""log 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("log")
def handle(ctx):
    """返回日志配置摘要."""
    ctx.reply(build_query_response_from_facade("log", ctx.get_diagnostics_facade()))
