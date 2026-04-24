"""
@file cmd_dx.py
@brief dx 相对位移指令处理器: 车体系 X 方向位移暂存
"""

from command.router import router


@router.command("dx")
def handle(ctx, value):
    """
    @brief 暂存车体系 X 方向相对位移(m), 在整包路由完成后统一转换坐标系

    @details
    不直接修改 ctx.last_cmd, 而是将车体系相对位移值存储在 ctx._pending_dx 中
    由 TransportCar._finalize_route() 在所有 key 路由完成后, 将车体系相对位移
    转换为世界系坐标增量, 再应用到世界系目标位置, 实现坐标转换的原子性
    新的整包命令可直接覆盖旧增量

    @param ctx   TransportCar 实例
    @param value 车体系 X 方向相对位移(m), 正值前进, 负值后退
    """
    ctx._pending_dx = value
