"""angle 偏航角指令处理器：绝对目标角（度），别名 yaw。"""
KEYS = ("angle", "yaw")


def handle(ctx, value: float) -> None:
    """
    设置绝对偏航角目标（度），锁定时忽略。

    参数：
        ctx:   TransportCar 实例。
        value: 目标偏航角（度，世界系）。
    """
    if ctx.command_lock:
        return
    ctx.last_cmd["angle"] = value
