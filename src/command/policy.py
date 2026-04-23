"""命令路由收口与健康字段辅助逻辑."""

import math


def _get_active_rear_flag(ctx) -> bool:
    """返回当前有效的后轮模式状态."""
    getter = getattr(ctx, "_get_active_rear_only_mode", None)
    if getter is not None:
        return bool(getter())
    return bool(getattr(ctx, "rear_only_mode", False))


def _has_active_translation_target(ctx) -> bool:
    """返回当前是否存在激活中的平移位置目标."""

    getter = getattr(ctx, "_has_active_translation_target", None)
    if getter is not None:
        return bool(getter())
    return ctx.last_cmd.get("x") is not None or ctx.last_cmd.get("y") is not None


def _has_active_rotation_target(ctx) -> bool:
    """返回当前是否存在激活中的转向位置目标."""

    getter = getattr(ctx, "_has_active_rotation_target", None)
    if getter is not None:
        return bool(getter())
    return ctx.last_cmd.get("angle") is not None


def build_command_health_fields(ctx) -> dict:
    """构造命令相关健康字段."""
    return {
        "lock": 1 if getattr(ctx, "command_lock", False) else 0,
        "rear": 1 if _get_active_rear_flag(ctx) else 0,
        "command_mode": getattr(ctx, "command_mode", "none"),
    }


def _apply_pending_relative_targets(ctx):
    """消费相对位姿暂存并写回绝对目标."""

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
    """清理平移位置式目标,让 `vx/vy` 直接接管."""

    ctx.last_cmd.pop("x", None)
    ctx.last_cmd.pop("y", None)
    ctx._pending_dx = None
    ctx._pending_dy = None


def _clear_rotation_targets(ctx) -> None:
    """清理转向位置式目标,让 `omega/w` 直接接管."""

    ctx.last_cmd.pop("angle", None)
    ctx._pending_d_angle = None


def finalize_command_route(ctx, dispatched, now_ms: int) -> None:
    """在整包命令完成分发后统一决定锁定与模式."""
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
