"""?health 查询处理器:返回运行期健康摘要."""

from command.router import router
from core.diagnostics import format_query_response


@router.query("health")
def handle(ctx):
    """通过当前查询响应串口回传系统健康诊断信息."""
    ctx.get_query_uart().write(
        format_query_response("health", ctx.build_health_snapshot())
    )
