"""omega 角速度指令处理器."""

from config.params import V_CMD_MAX
from control.pid_math import clamp
from services.commanding.router import router


@router.command("omega", "w")
def handle(ctx, value):
    """设置角速度目标."""
    if ctx.session.command_lock:
        return
    ctx.session.last_cmd["omega"] = clamp(value, -V_CMD_MAX, V_CMD_MAX)
