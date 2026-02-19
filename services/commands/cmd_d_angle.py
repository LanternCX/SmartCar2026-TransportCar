"""d_angle 相对偏航角指令处理器,别名 dyaw / da."""
from services.command_router import router


@router.command("d_angle", "dyaw", "da")
def handle(ctx, value: float) -> None:
    """
    暂存相对偏航角增量(度),锁定时忽略.

    实际的角度叠加由 TransportCar._finalize_route() 在所有 key 路由完成后统一执行.

    参数:
        ctx:   TransportCar 实例.
        value: 相对偏航角增量(度).
    """
    if ctx.command_lock:
        return
    ctx._pending_d_angle = value
