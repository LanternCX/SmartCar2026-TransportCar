"""print 调试打印指令处理器：透传消息到 uart3。"""
from services.command_router import router


@router.command("print")
def handle(ctx, value: str) -> None:
    """
    将 value 字符串透传输出到 uart3（调试用途）。

    参数：
        ctx:   TransportCar 实例。
        value: 要打印的字符串内容（保留原始格式，不做类型转换）。
    """
    ctx.uart3.write("%s\r\n" % value)
