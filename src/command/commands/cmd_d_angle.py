"""
@file cmd_d_angle.py
@brief d_angle 相对偏航角指令处理器, 别名 dyaw / da
"""

from command.router import router


@router.command("d_angle", "dyaw", "da")
def handle(ctx, value):
    """
    @brief 暂存相对偏航角增量(度), 在整包路由完成后统一应用

    @details
    不直接修改 ctx.last_cmd, 而是将增量值存储在 ctx._pending_d_angle 中
    由 TransportCar._finalize_route() 在所有 key 路由完成后, 将该增量应用到
    当前目标角, 实现相对角度调整的原子性操作.新的整包命令可直接覆盖旧增量

    @param ctx   TransportCar 实例
    @param value 相对偏航角增量(度), 正值逆时针, 负值顺时针
    """
    ctx._pending_d_angle = value
