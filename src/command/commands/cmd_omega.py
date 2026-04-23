"""
@file cmd_omega.py
@brief omega 角速度指令处理器, 目标角速度(度/s), 别名 w
"""

from config import params as _params
from command.router import router
from control.pid_math import clamp


# @brief 角速度最大限值(度/s), 从配置文件读取, 确保角速度指令不超范围
V_CMD_MAX = getattr(_params, "V_CMD_MAX")


@router.command("omega", "w")
def handle(ctx, value):
    """
    @brief 设置角速度目标(度/s), 进入角速度模式并清除角度指令

    @details
    将限幅后的角速度值存储到 ctx.last_cmd["omega"], 接管任何旧的角度指令
    输入值自动限幅到 ±V_CMD_MAX 范围内, 防止超出转向能力
    该命令设置的是即时角速度目标, 控制层将实时跟踪该角速度, 无需等待整包路由

    @param ctx   TransportCar 实例
    @param value 角速度(度/s), 自动限幅到 [-V_CMD_MAX, V_CMD_MAX]
                 正值逆时针, 负值顺时针
    """
    ctx.last_cmd["omega"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
