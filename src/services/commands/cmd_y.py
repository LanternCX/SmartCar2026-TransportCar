"""y 坐标指令处理器:绝对 Y 坐标目标(世界系)."""

from services.command_router import router


@router.command("y")
def handle(ctx, value):
    """
    设置绝对 Y 坐标目标(m),允许新位置命令直接接管旧目标,同时清除 vy 速度意图以进入位置模式.

    参数:
        ctx:   TransportCar 实例.
        value: Y 坐标目标(m).
    """
    ctx.last_cmd["y"] = value
    ctx.last_cmd.pop("vy", None)
