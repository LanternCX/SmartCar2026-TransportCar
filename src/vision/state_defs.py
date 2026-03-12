"""视觉状态机结构定义与默认注册."""

from vision.state_registry import StateSpec, vision_state_registry


class SMState:
    """视觉状态机状态常量."""

    IDLE = 0
    ALIGN_ANGLE = 1
    ALIGN_DIST = 2
    ALIGN_DX = 3
    ORBITING = 4
    PUSHING = 5
    RETURNING = 6
    DONE = 7


class VisionTransitionReason:
    """视觉状态机迁移原因常量."""

    RESET = "reset"
    OBSERVATION_LOST = "observation_lost"
    OBSERVATION_ACQUIRED = "observation_acquired"
    ANGLE_ALIGNED_STABLE = "angle_aligned_stable"
    ANGLE_ERROR_REENTRY = "angle_error_reentry"
    DISTANCE_ALIGNED_STABLE = "distance_aligned_stable"
    DISTANCE_NOT_READY = "distance_not_ready"
    ENTER_PUSHING = "enter_pushing"
    HEADING_NOT_READY = "heading_not_ready"
    HEADING_ALIGNED = "heading_aligned"
    PUSH_DISTANCE_REACHED = "push_distance_reached"
    RETURN_HEADING_REACHED = "return_heading_reached"
    DONE_HOLD_ELAPSED = "done_hold_elapsed"
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
