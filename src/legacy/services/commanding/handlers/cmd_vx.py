"""vx 速度指令处理器."""

from config.params import V_CMD_MAX
from control.pid_math import clamp
from services.commanding.router import router


@router.command("vx")
def handle(ctx, value):
    """设置车体系 X 方向速度目标."""
    if ctx.session.command_lock:
        return
    ctx.session.last_cmd["vx"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
