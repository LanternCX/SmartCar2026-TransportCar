"""x 坐标指令处理器:绝对 X 坐标目标(世界系)."""
from services.command_router import router


@router.command("x")
def handle(ctx, value):
    """
    设置绝对 X 坐标目标(m),锁定时忽略.同时清除 vx 速度意图以进入位置模式.

    参数:
        ctx:   TransportCar 实例.
        value: X 坐标目标(m).
    """
    if ctx.command_lock:
        return
    ctx.last_cmd["x"] = value
    ctx.last_cmd.pop("vx", None)
