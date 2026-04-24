"""
@file cmd_x.py
@brief x 坐标指令处理器: 绝对 X 坐标目标(世界系)
"""

from command.router import router


@router.command("x")
def handle(ctx, value):
    """
    @brief 设置绝对 X 坐标目标(m), 进入位置模式并清除速度指令

    @details
    将 value 存储到 ctx.last_cmd["x"] 以便在 _finalize_route() 后由控制层读取
    同时移除字典中的 "vx" 键确保从速度模式切换到位置模式, 旧的 X 速度指令
    被新的 X 位置指令接管, 后续命令将按照位置模式执行

    @param ctx   TransportCar 实例
    @param value 目标 X 坐标(m, 世界系), 允许为负值
    """
    ctx.last_cmd["x"] = value
    ctx.last_cmd.pop("vx", None)
