"""dx 相对位移指令处理器:车体系 X 方向位移暂存."""
from services.command_router import router


@router.command("dx")
def handle(ctx, value):
    """
    暂存车体系 X 方向相对位移(m),锁定时忽略.

    实际的世界坐标转换由 TransportCar._finalize_route() 在所有 key 路由完成后统一执行.

    参数:
        ctx:   TransportCar 实例.
        value: 车体系 X 方向相对位移(m).
    """
    if ctx.command_lock:
        return
    ctx._pending_dx = value
