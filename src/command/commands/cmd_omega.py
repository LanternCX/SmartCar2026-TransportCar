"""omega 角速度指令处理器,别名 w."""

from config import params as _params
from command.router import router
from control.pid_math import clamp


V_CMD_MAX = getattr(_params, "V_CMD_MAX")


@router.command("omega", "w")
def handle(ctx, value):
    """
    设置角速度目标(度/s),允许新速度命令直接接管旧角度目标.

    参数:
        ctx:   TransportCar 实例.
        value: 角速度(度/s),自动限幅到 ±V_CMD_MAX.
    """
    ctx.last_cmd["omega"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
