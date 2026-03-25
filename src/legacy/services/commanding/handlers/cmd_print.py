"""print 调试输出指令处理器."""

from services.commanding.router import router


@router.command("print", value_type="raw")
def handle(ctx, value):
    """透传文本到 uart3."""
    ctx.uart3.write("%s\r\n" % value)
