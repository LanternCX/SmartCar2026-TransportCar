"""rear 后轮模式切换指令处理器。"""
KEYS = ("rear",)


def handle(ctx, value: float) -> None:
    """
    切换后轮专用模式（非零为启用），锁定时忽略。

    模式变更标志 _rear_mode_changed 由 _finalize_route() 读取以触发 command_lock。

    参数：
        ctx:   TransportCar 实例。
        value: 非零表示启用后轮模式，零表示全向模式。
    """
    if ctx.command_lock:
        return
    new_mode = value != 0
    ctx._rear_mode_changed = new_mode != ctx.rear_only_mode
    ctx.rear_only_mode = new_mode
    ctx.uart3.write("Rear Only Mode: %s\r\n" % str(ctx.rear_only_mode))
