"""print 调试命令处理器."""

from command.router import router


@router.command("print")
def handle(ctx, value):
    """
    接受调试文本参数,但运行时不直接输出.

    参数:
        ctx:   TransportCar 实例.
        value: 要打印的字符串内容(保留原始格式,不做类型转换).
    """
    _ = ctx, value
