"""d_angle 相对偏航角指令处理器,别名 dyaw / da."""

from command.router import router


@router.command("d_angle", "dyaw", "da")
def handle(ctx, value):
    """
    暂存相对偏航角增量(度),允许新整包命令覆盖旧目标.

    实际的角度叠加由 TransportCar._finalize_route() 在所有 key 路由完成后统一执行.

    参数:
        ctx:   TransportCar 实例.
        value: 相对偏航角增量(度).
    """
    ctx._pending_d_angle = value
