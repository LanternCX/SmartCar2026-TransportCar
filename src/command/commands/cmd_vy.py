"""vy 速度指令处理器:Y 方向速度(车体系)."""

from config import params as _params
from command.router import router
from control.pid_math import clamp


V_CMD_MAX = getattr(_params, "V_CMD_MAX")


@router.command("vy")
def handle(ctx, value):
    """
    设置 Y 方向速度目标(车体系,脉冲/s),允许新速度命令直接接管旧目标.

    参数:
        ctx:   TransportCar 实例.
        value: 速度值(脉冲/s),自动限幅到 ±V_CMD_MAX.
    """
    ctx.last_cmd["vy"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
