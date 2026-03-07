"""?vision 查询处理器:返回视觉状态机摘要."""

from services.command_router import router
from services.diagnostics import format_query_response


@router.query("vision")
def handle(ctx):
    """通过 uart6 回传视觉观测与目标摘要."""
    ctx.uart6.write(format_query_response("vision", ctx.build_vision_snapshot()))
