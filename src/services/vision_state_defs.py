"""视觉状态机结构定义与默认注册."""

from services.vision_state_registry import StateSpec, vision_state_registry


class SMState:
    """视觉状态机状态常量."""

    # 空闲态,等待视觉目标进入
    IDLE = 0
    # 角度对齐态,优先消除图像横向偏差
    ALIGN_ANGLE = 1
    # 距离对齐态,沿车体纵向修正目标距离
    ALIGN_DIST = 2
    # 最终横移对齐态,为推行前做最后位置确认
    ALIGN_DX = 3
    # 绕行态,仅调整推行朝向
    ORBITING = 4
    # 推行态,按固定方向推进目标
    PUSHING = 5
    # 返回态,将车头转回反向朝向
    RETURNING = 6
    # 完成态,短暂停留后再回空闲
    DONE = 7


class VisionTransitionReason:
    """视觉状态机迁移原因常量."""

    # 外部显式重置状态机
    RESET = "reset"
    # 对齐阶段丢失视觉观测
    OBSERVATION_LOST = "observation_lost"
    # 空闲态首次获取到视觉观测
    OBSERVATION_ACQUIRED = "observation_acquired"
    # 角度对齐稳定达标,切入距离对齐
    ANGLE_ALIGNED_STABLE = "angle_aligned_stable"
    # 横向误差重新超限,回退到角度对齐
    ANGLE_ERROR_REENTRY = "angle_error_reentry"
    # 距离对齐稳定达标,切入最终横移对齐
    DISTANCE_ALIGNED_STABLE = "distance_aligned_stable"
    # 距离再次偏离,回退到距离对齐
    DISTANCE_NOT_READY = "distance_not_ready"
    # 最终对齐完成,进入推行态
    ENTER_PUSHING = "enter_pushing"
    # 推行朝向未达标,进入绕行态
    HEADING_NOT_READY = "heading_not_ready"
    # 绕行朝向已达标,返回最终横移对齐
    HEADING_ALIGNED = "heading_aligned"
    # 推行距离达到阈值,切入返回态
    PUSH_DISTANCE_REACHED = "push_distance_reached"
    # 返回朝向已达标,进入完成态
    RETURN_HEADING_REACHED = "return_heading_reached"
    # 完成态停留时间结束,回到空闲态
    DONE_HOLD_ELAPSED = "done_hold_elapsed"
    # 命中兜底保护分支,强制退回空闲态
    UNKNOWN_STATE_GUARD = "unknown_state_guard"


class _StateNamespace:
    """视觉状态对象命名空间."""

    IDLE = StateSpec(SMState.IDLE, "IDLE")
    ALIGN_ANGLE = StateSpec(SMState.ALIGN_ANGLE, "ALIGN_ANGLE")
    ALIGN_DIST = StateSpec(SMState.ALIGN_DIST, "ALIGN_DIST")
    ALIGN_DX = StateSpec(SMState.ALIGN_DX, "ALIGN_DX")
    ORBITING = StateSpec(SMState.ORBITING, "ORBITING")
    PUSHING = StateSpec(SMState.PUSHING, "PUSHING")
    RETURNING = StateSpec(SMState.RETURNING, "RETURNING")
    DONE = StateSpec(SMState.DONE, "DONE")


SM = _StateNamespace()


def _register_state(attr_name, state_id):
    """创建并注册一个状态对象."""
    state = vision_state_registry.register_state(StateSpec(state_id, attr_name))
    setattr(SM, attr_name, state)
    return state


def _register_defaults():
    """注册默认视觉状态与迁移包装对象."""
    idle = _register_state("IDLE", SMState.IDLE)
    align_angle = _register_state("ALIGN_ANGLE", SMState.ALIGN_ANGLE)
    align_dist = _register_state("ALIGN_DIST", SMState.ALIGN_DIST)
    align_dx = _register_state("ALIGN_DX", SMState.ALIGN_DX)
    orbiting = _register_state("ORBITING", SMState.ORBITING)
    pushing = _register_state("PUSHING", SMState.PUSHING)
    returning = _register_state("RETURNING", SMState.RETURNING)
    done = _register_state("DONE", SMState.DONE)

    idle.bind("RESET", VisionTransitionReason.RESET)
    idle.bind("OBSERVATION_LOST", VisionTransitionReason.OBSERVATION_LOST)
    idle.bind("DONE_HOLD_ELAPSED", VisionTransitionReason.DONE_HOLD_ELAPSED)
    idle.bind("UNKNOWN_STATE_GUARD", VisionTransitionReason.UNKNOWN_STATE_GUARD)

    align_angle.bind(
        "OBSERVATION_ACQUIRED", VisionTransitionReason.OBSERVATION_ACQUIRED
    )
    align_angle.bind("ANGLE_ERROR_REENTRY", VisionTransitionReason.ANGLE_ERROR_REENTRY)

    align_dist.bind("ANGLE_ALIGNED_STABLE", VisionTransitionReason.ANGLE_ALIGNED_STABLE)
    align_dist.bind("DISTANCE_NOT_READY", VisionTransitionReason.DISTANCE_NOT_READY)

    align_dx.bind(
        "DISTANCE_ALIGNED_STABLE", VisionTransitionReason.DISTANCE_ALIGNED_STABLE
    )
    align_dx.bind("HEADING_ALIGNED", VisionTransitionReason.HEADING_ALIGNED)

    orbiting.bind("HEADING_NOT_READY", VisionTransitionReason.HEADING_NOT_READY)
    pushing.bind("ENTER_PUSHING", VisionTransitionReason.ENTER_PUSHING)
    returning.bind(
        "PUSH_DISTANCE_REACHED", VisionTransitionReason.PUSH_DISTANCE_REACHED
    )
    done.bind("RETURN_HEADING_REACHED", VisionTransitionReason.RETURN_HEADING_REACHED)


_register_defaults()
