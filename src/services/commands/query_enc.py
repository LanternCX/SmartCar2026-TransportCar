"""?enc 查询处理器:返回编码器观测摘要."""

from services.command_router import router
from services.diagnostics import format_query_response


@router.query("enc")
def handle(ctx):
    """通过 uart6 回传编码器诊断信息."""
    ctx.uart6.write(format_query_response("enc", ctx.build_encoder_snapshot()))
