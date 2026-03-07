"""?health 查询处理器:返回运行期健康摘要."""

from services.command_router import router
from services.diagnostics import format_query_response


@router.query("health")
def handle(ctx):
    """通过 uart6 回传系统健康诊断信息."""
    ctx.uart6.write(format_query_response("health", ctx.build_health_snapshot()))
