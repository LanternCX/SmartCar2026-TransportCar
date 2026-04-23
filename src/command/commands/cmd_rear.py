"""
@file cmd_rear.py
@brief rear 后轮模式切换指令处理器, 全向/专向后轮模式切换
"""

from command.router import router


@router.command("rear")
def handle(ctx, value):
    """
    @brief 切换后轮专用模式与全向模式, 记录模式变更标志

    @details
    非零值启用后轮专用模式, 零值切换回全向模式.该命令每次被调用时,
    通过比较新模式与当前模式, 在 ctx._rear_mode_changed 中记录是否发生了变更
    TransportCar._finalize_route() 将读取此标志以触发 command_lock 锁定,
    确保模式切换时停止当前运动, 防止运动学模型突变导致的不连续性
    新的整包命令可直接覆盖旧模式

    @param ctx   TransportCar 实例
    @param value 非零表示启用后轮专用模式, 零表示启用全向模式

    @details_variables
    - ctx._rear_mode_changed (bool): 标记本次命令后是否改变了模式
    - ctx.rear_only_mode (bool): 当前运动模式(True=后轮专用, False=全向)
    """
    new_mode = value != 0
    ctx._rear_mode_changed = new_mode != ctx.rear_only_mode
    ctx.rear_only_mode = new_mode
