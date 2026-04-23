"""
@file cmd_lock.py
@brief lock 整包锁定语义指令处理器, 请求进入/退出运动锁定
"""

from command.router import router


@router.command("lock")
def handle(ctx, value):
    """
    @brief 记录整包对运动锁定状态的请求, 由后续路由完成处理应用

    @details
    非零值表示请求进入锁定模式(停止运动, 不接收新目标), 零值表示请求解除锁定
    该请求被暂存到 ctx._pending_lock, 由 TransportCar._finalize_route() 在所有
    key 路由完成后读取并实际应用到 ctx.command_lock, 实现锁定状态变更的原子性

    @param ctx   TransportCar 实例
    @param value 非零表示要求进入锁定模式, 零表示解除锁定

    @variables
    - ctx._pending_lock (bool|None): 暂存的锁定请求状态
    """
    ctx._pending_lock = value != 0
