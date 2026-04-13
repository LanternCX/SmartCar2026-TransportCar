"""dx 相对位移指令处理器:车体系 X 方向位移暂存."""

from services.command_router import router


@router.command("dx")
def handle(ctx, value):
    """
    暂存车体系 X 方向相对位移(m),允许新整包命令覆盖旧目标.

    实际的世界坐标转换由 TransportCar._finalize_route() 在所有 key 路由完成后统一执行.

    参数:
        ctx:   TransportCar 实例.
        value: 车体系 X 方向相对位移(m).
    """
    ctx._pending_dx = value
