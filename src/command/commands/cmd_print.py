"""
@file cmd_print.py
@brief print 调试指令处理器, 接受但不输出调试文本
"""

from command.router import router


@router.command("print")
def handle(ctx, value):
    """
    @brief 接收调试命令但不执行输出操作, 作为命令路由的占位处理器

    @details
    该命令用于调试阶段验证命令解析和路由的完整性, 实际输出由上层应用决定
    参数被忽略以确保命令不会产生副作用, 保持系统状态不变

    @param ctx   TransportCar 实例
    @param value 调试文本内容(保留原始格式, 不做任何类型转换或处理)
    """
    _ = ctx, value
