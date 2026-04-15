"""命令路由收口与健康字段辅助逻辑."""

import math


def _get_active_rear_flag(ctx) -> bool:
    """返回当前有效的后轮模式状态."""
    getter = getattr(ctx, "_get_active_rear_only_mode", None)
    if getter is not None:
        return bool(getter())
    return bool(getattr(ctx, "rear_only_mode", False))


def build_command_health_fields(ctx) -> dict:
    """构造命令相关健康字段."""
    return {
        "lock": 1 if getattr(ctx, "command_lock", False) else 0,
        "rear": 1 if _get_active_rear_flag(ctx) else 0,
        "command_mode": getattr(ctx, "command_mode", "none"),
    }


def _apply_pending_relative_targets(ctx) -> bool:
    """消费相对位姿暂存并写回绝对目标."""
    is_position_packet = False

    if getattr(ctx, "_pending_d_angle", None) is not None:
        ctx.last_cmd["angle"] = float(ctx.heading_target) + float(ctx._pending_d_angle)
        ctx.last_cmd.pop("omega", None)
        ctx._pending_d_angle = None
        is_position_packet = True

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
        is_position_packet = True

    return is_position_packet


def _clear_position_targets(ctx) -> None:
    """清理位置式目标,让速度命令直接接管."""
    ctx.last_cmd.pop("x", None)
    ctx.last_cmd.pop("y", None)
    ctx.last_cmd.pop("angle", None)
    ctx._pending_dx = None
    ctx._pending_dy = None
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

    is_position_packet = _apply_pending_relative_targets(ctx)
    if not is_position_packet:
        is_position_packet = (
            "x" in dispatched
            or "y" in dispatched
            or "angle" in dispatched
            or "yaw" in dispatched
        )

    is_velocity_packet = (
        "vx" in dispatched
        or "vy" in dispatched
        or "omega" in dispatched
        or "w" in dispatched
    )
    if is_velocity_packet:
        _clear_position_targets(ctx)
        ctx.command_lock = False
        ctx.command_mode = "none"
    elif is_position_packet or rear_mode_changed:
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
    else:
        ctx.command_lock = False
        ctx.command_mode = "none"

    ctx._pending_lock = None
    if hasattr(ctx, "last_rear_mode"):
        ctx.last_rear_mode = bool(getattr(ctx, "rear_only_mode", False))

    if not is_position_packet and hasattr(ctx, "_inverse_kinematics"):
        vx_val = ctx.last_cmd.get("vx") or 0.0
        vy_val = ctx.last_cmd.get("vy") or 0.0
        omega_val = ctx.last_cmd.get("omega") or 0.0
        ctx._inverse_kinematics(vx_val, vy_val, omega_val)
