"""lock 查询处理器."""

from services.commanding.router import router
from services.diagnostics import build_query_response_from_facade


@router.query("lock")
def handle(ctx):
    """返回当前命令锁定状态."""
    ctx.reply(build_query_response_from_facade("lock", ctx.get_diagnostics_facade()))
