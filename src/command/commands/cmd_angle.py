"""
@file cmd_angle.py
@brief angle 偏航角指令处理器: 绝对目标角(度), 别名 yaw
"""

from command.router import router


@router.command("angle", "yaw")
def handle(ctx, value):
    """
    @brief 设置绝对偏航角目标(度), 进入角度模式并清除角速度指令

    @details
    将 value 存储到 ctx.last_cmd["angle"] 作为世界系目标角
    同时移除字典中的 "omega" 键确保从角速度模式切换到绝对角度模式,
    后续控制层将围绕该目标角进行 PID 调控

    @param ctx   TransportCar 实例
    @param value 目标偏航角(度, 世界系, -180~180 范围内)
    """
    ctx.last_cmd["angle"] = value
    ctx.last_cmd.pop("omega", None)
