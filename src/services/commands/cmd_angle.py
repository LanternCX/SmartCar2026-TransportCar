"""angle 偏航角指令处理器:绝对目标角(度),别名 yaw."""

from services.command_router import router


@router.command("angle", "yaw")
def handle(ctx, value):
    """
    设置绝对偏航角目标(度),允许新角度命令直接接管旧目标.

    参数:
        ctx:   TransportCar 实例.
        value: 目标偏航角(度,世界系).
    """
    ctx.last_cmd["angle"] = value
    ctx.last_cmd.pop("omega", None)
