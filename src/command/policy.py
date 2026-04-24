"""命令路由收口与健康字段辅助逻辑

本模块负责命令路由的最终处理, 包括相对位姿目标的消费与转换、
位置/速度模式的冲突解决、锁定状态的判定以及健康字段的构造
"""

import math


def _get_active_rear_flag(ctx) -> bool:
    """获取当前有效的后轮模式状态

    @param ctx: 控制器上下文对象, 包含 rear_only_mode 状态
    @return: 若后轮模式激活返回 True, 否则返回 False
    """
    getter = getattr(ctx, "_get_active_rear_only_mode", None)
    if getter is not None:
        return bool(getter())
    return bool(getattr(ctx, "rear_only_mode", False))


def _has_active_translation_target(ctx) -> bool:
    """检查是否存在激活中的平移位置目标

    @param ctx: 控制器上下文对象, 包含 last_cmd 命令状态
    @return: 若存在 x 或 y 位置目标返回 True, 否则返回 False
    """
    getter = getattr(ctx, "_has_active_translation_target", None)
    if getter is not None:
        return bool(getter())
    return ctx.last_cmd.get("x") is not None or ctx.last_cmd.get("y") is not None


def _has_active_rotation_target(ctx) -> bool:
    """检查是否存在激活中的转向位置目标

    @param ctx: 控制器上下文对象, 包含 last_cmd 命令状态
    @return: 若存在 angle 角度目标返回 True, 否则返回 False
    """
    getter = getattr(ctx, "_has_active_rotation_target", None)
    if getter is not None:
        return bool(getter())
    return ctx.last_cmd.get("angle") is not None


def build_command_health_fields(ctx) -> dict:
    """构造命令相关健康字段字典

    @param ctx: 控制器上下文对象
    @return: 包含锁定状态、后轮模式、命令模式的字典
    """
    return {
        "lock": 1 if getattr(ctx, "command_lock", False) else 0,
        "rear": 1 if _get_active_rear_flag(ctx) else 0,
        "command_mode": getattr(ctx, "command_mode", "none"),
    }


def _apply_pending_relative_targets(ctx):
    """消费相对位姿暂存并转换为绝对目标写入命令

    将暂存的相对位移(dx, dy)和相对角度(d_angle)转换为
    世界坐标系下的绝对位置目标, 写入 last_cmd

    @param ctx: 控制器上下文对象, 包含 _pending_dx、_pending_dy、
                _pending_d_angle 等暂存字段以及 odometry、heading_target
    @return: (has_translation_position, has_rotation_position) 元组
             分别表示是否存在平移和旋转位置目标
    """
    has_translation_position = False
    has_rotation_position = False

    if getattr(ctx, "_pending_d_angle", None) is not None:
        ctx.last_cmd["angle"] = float(ctx.heading_target) + float(ctx._pending_d_angle)
        ctx.last_cmd.pop("omega", None)
        ctx._pending_d_angle = None
        has_rotation_position = True

    if (
        getattr(ctx, "_pending_dx", None) is not None
        or getattr(ctx, "_pending_dy", None) is not None
    ):
        dx_body = float(ctx._pending_dx) if ctx._pending_dx is not None else 0.0
        dy_body = float(ctx._pending_dy) if ctx._pending_dy is not None else 0.0
        theta_rad = math.radians(float(ctx.heading_est))
        cos_t = math.cos(theta_rad)
        sin_t = math.sin(theta_rad)
        ctx.last_cmd["x"] = float(ctx.odometry.x) + dx_body * cos_t - dy_body * sin_t
        ctx.last_cmd["y"] = float(ctx.odometry.y) + dx_body * sin_t + dy_body * cos_t
        ctx.last_cmd.pop("vx", None)
        ctx.last_cmd.pop("vy", None)
        ctx._pending_dx = None
        ctx._pending_dy = None
        has_translation_position = True

    return has_translation_position, has_rotation_position


def _clear_translation_targets(ctx) -> None:
    """清理平移位置式目标, 切换到速度控制模式

    清除 x、y 位置目标以及暂存的相对位移, 使得 vx/vy 速度命令
    可以直接接管控制

    @param ctx: 控制器上下文对象
    @return: None
    """
    ctx.last_cmd.pop("x", None)
    ctx.last_cmd.pop("y", None)
    ctx._pending_dx = None
    ctx._pending_dy = None


def _clear_rotation_targets(ctx) -> None:
    """清理转向位置式目标, 切换到角速度控制模式

    清除 angle 角度目标以及暂存的相对角度, 使得 omega/w 角速度命令
    可以直接接管控制

    @param ctx: 控制器上下文对象
    @return: None
    """
    ctx.last_cmd.pop("angle", None)
    ctx._pending_d_angle = None


def finalize_command_route(ctx, dispatched, now_ms: int) -> None:
    """在整包命令完成分发后统一决定锁定与模式

    该函数是命令路由的最终处理点, 负责:
    - 处理 reset 命令的特殊逻辑
    - 消费相对位姿暂存
    - 解决位置模式与速度模式的冲突
    - 根据新目标或模式变化决定是否进入锁定状态
    - 更新命令模式标识

    @param ctx: 控制器上下文对象
    @param dispatched: 本次命令包中已分发的字段集合
    @param now_ms: 当前时间戳(毫秒), 用于记录锁定开始时间
    @return: None
    """
    if "reset" in dispatched:
        ctx._pending_lock = None
        ctx.command_mode = "none"
        return

    pending_lock = getattr(ctx, "_pending_lock", None)
    rear_mode_changed = bool(getattr(ctx, "_rear_mode_changed", False))
    ctx._rear_mode_changed = False

    if "angle" in dispatched or "yaw" in dispatched:
        ctx.last_cmd.pop("omega", None)

    (
        has_translation_position_packet,
        has_rotation_position_packet,
    ) = _apply_pending_relative_targets(ctx)
    if not has_translation_position_packet:
        has_translation_position_packet = "x" in dispatched or "y" in dispatched
    if not has_rotation_position_packet:
        has_rotation_position_packet = "angle" in dispatched or "yaw" in dispatched

    has_translation_velocity_packet = "vx" in dispatched or "vy" in dispatched
    has_rotation_velocity_packet = "omega" in dispatched or "w" in dispatched

    if has_translation_velocity_packet:
        _clear_translation_targets(ctx)
    if has_rotation_velocity_packet:
        _clear_rotation_targets(ctx)

    has_active_translation_target = _has_active_translation_target(ctx)
    has_active_rotation_target = _has_active_rotation_target(ctx)
    has_active_pose_target = has_active_translation_target or has_active_rotation_target

    has_new_pose_target = (
        has_translation_position_packet and has_active_translation_target
    ) or (has_rotation_position_packet and has_active_rotation_target)

    if has_new_pose_target or rear_mode_changed:
        if pending_lock is None:
            should_lock = True
        else:
            should_lock = bool(pending_lock)
        ctx.command_lock = should_lock
        if should_lock:
            ctx.command_mode = "locked"
            ctx.lock_start_time = int(now_ms)
        else:
            ctx.command_mode = "unlocked"
    elif has_active_pose_target:
        ctx.command_mode = "locked" if ctx.command_lock else "unlocked"
    else:
        ctx.command_lock = False
        ctx.command_mode = "none"

    ctx._pending_lock = None
    if hasattr(ctx, "last_rear_mode"):
        ctx.last_rear_mode = bool(getattr(ctx, "rear_only_mode", False))

    if not has_active_pose_target and hasattr(ctx, "_inverse_kinematics"):
        vx_val = ctx.last_cmd.get("vx") or 0.0
        vy_val = ctx.last_cmd.get("vy") or 0.0
        omega_val = ctx.last_cmd.get("omega") or 0.0
        ctx._inverse_kinematics(vx_val, vy_val, omega_val)
