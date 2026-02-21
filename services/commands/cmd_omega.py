"""omega 角速度指令处理器,别名 w."""
from services.command_router import router
from control.pid_math import clamp
from config.params import V_CMD_MAX


@router.command("omega", "w")
def handle(ctx, value):
    """
    设置角速度目标(度/s),锁定时忽略.

    参数:
        ctx:   TransportCar 实例.
        value: 角速度(度/s),自动限幅到 ±V_CMD_MAX.
    """
    if ctx.command_lock:
        return
    ctx.last_cmd["omega"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
