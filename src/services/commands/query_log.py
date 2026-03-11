"""?log 运行时日志配置查询处理器."""

from services.command_router import router
from diagnostics.manager import LogQueryContext


@router.query("log")
def handle(ctx: LogQueryContext) -> None:
    """通过当前查询响应串口返回日志配置摘要."""
    ctx.get_query_uart().write(ctx.logger_manager.build_query_response())
