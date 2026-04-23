"""
@file cmd_vy.py
@brief vy 速度指令处理器, 车体系 Y 方向速度目标(脉冲/s)
"""

from config import params as _params
from command.router import router
from control.pid_math import clamp


# @brief Y 方向最大速度限值(脉冲/s), 从配置文件读取, 确保电机指令不超范围
V_CMD_MAX = getattr(_params, "V_CMD_MAX")


@router.command("vy")
def handle(ctx, value):
    """
    @brief 设置车体系 Y 方向速度目标(脉冲/s), 进入速度模式并清除位置指令

    @details
    将限幅后的速度值存储到 ctx.last_cmd["vy"], 接管任何旧的 Y 速度指令
    输入值自动限幅到 ±V_CMD_MAX 范围内, 防止超出电机驱动能力
    该命令设置的是即时速度目标, 控制层将实时跟踪该速度, 无需等待整包路由

    @param ctx   TransportCar 实例
    @param value 速度值(脉冲/s), 自动限幅到 [-V_CMD_MAX, V_CMD_MAX]
                 正值左移, 负值右移
    """
    ctx.last_cmd["vy"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
