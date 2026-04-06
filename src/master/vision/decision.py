"""主车二维控制决策.

@file src/master/vision/decision.py
"""

_package_name = str(globals().get("__package__", ""))

if "." in _package_name:
    from .. import runtime_params
    from ..protocol import build_follow_command
else:
    import runtime_params
    from protocol import build_follow_command


class Decision:
    def __init__(
        self,
        phase,
        selected_target,
        self_target,
        assistant_target,
        assistant_state,
        assistant_command,
        self_base_state,
    ):
        self.phase = str(phase)
        self.selected_target = str(selected_target)
        self.self_target = dict(self_target)
        self.assistant_target = dict(assistant_target)
        self.assistant_state = dict(assistant_state)
        self.assistant_command = str(assistant_command)
        self.self_base_state = dict(self_base_state)


def _build_self_base_state(snapshot):
    heading_deg = float(snapshot.get("heading_est_deg", 0.0))
    odom = snapshot.get("odom", (0.0, 0.0))
    return {
        "heading_deg": heading_deg,
        "yaw_rate_deg_s": float(snapshot.get("yaw_rate_deg_s", 0.0)),
        "odom_x": float(odom[0]),
        "odom_y": float(odom[1]),
        "base_ok": 1 if snapshot.get("base_ok", 0) else 0,
    }


def decide_from_state(state_output):
    """在缺少新视觉输入时生成保守决策.

    @brief 把运行时已有状态包装成空闲决策, 让下游输出链保持字段稳定。
    """

    control_seq = int(state_output.get("control_seq", 0))
    return _build_idle_decision(
        control_seq=control_seq,
        phase=str(state_output.get("phase", "MARKER_MISSING")),
        selected_target=str(state_output.get("selected_target", "idle")),
    )


def _build_idle_decision(
    control_seq,
    phase="MARKER_MISSING",
    selected_target="idle",
    target_valid=0,
    target_fresh=0,
    self_base_snapshot=None,
    reason="",
):
    """构造不驱动辅车跟随的空闲决策对象.

    @brief 统一集中空目标、阶段状态和基础回包字段, 避免多处各写一套默认值。
    """

    assistant_target = {"valid": 0, "dx": 0.0, "dy": 0.0}
    assistant_state = {
        "phase": phase,
        "selected_target": selected_target,
        "target_valid": int(target_valid),
        "target_fresh": int(target_fresh),
    }
    if self_base_snapshot is None:
        self_base_snapshot = {}
    self_base_state = _build_self_base_state(self_base_snapshot)
    return Decision(
        phase=phase,
        selected_target=selected_target,
        self_target={"kind": "hold"},
        assistant_target=assistant_target,
        assistant_state=assistant_state,
        assistant_command=build_follow_command(
            seq=control_seq,
            valid=0,
            dx=0.0,
            dy=0.0,
            reason=reason,
        ),
        self_base_state=self_base_state,
    )


def _resolve_idle_reason(observation, phase):
    source_status = str(observation.get("source_status", "")).strip()
    if source_status == "invalid":
        return "parse_invalid"
    if source_status == "active" and int(observation.get("valid", 0)) != 1:
        return "vision_invalid"
    if int(observation.get("fresh", 1)) != 1 or int(observation.get("stale", 0)) == 1:
        return "stale"
    if phase == "CENTER_HOLD":
        return "center_hold"
    if source_status == "missing":
        return "missing"
    return "missing"


def decide_from_observation(observation, state_machine=None):
    """根据视觉观测生成主车对外决策结果.

    @brief 这里只决定是否进入跟随输出以及给辅车的目标量, 不负责状态机推进。
    """

    _ = state_machine
    control_seq = int(observation.get("control_seq", 0))
    phase = str(observation.get("phase", "MARKER_MISSING"))
    selected_target = str(observation.get("selected_target", "idle"))
    if int(observation.get("valid", 0)) != 1:
        return _build_idle_decision(
            control_seq,
            phase=phase,
            selected_target=selected_target,
            self_base_snapshot=observation,
            reason=_resolve_idle_reason(observation, phase),
        )
    if int(observation.get("fresh", 1)) != 1 or int(observation.get("stale", 0)) == 1:
        return _build_idle_decision(
            control_seq,
            phase=phase,
            selected_target=selected_target,
            self_base_snapshot=observation,
            reason=_resolve_idle_reason(observation, phase),
        )
    if phase != "TRACKING":
        return _build_idle_decision(
            control_seq,
            phase=phase,
            selected_target=selected_target,
            target_valid=1,
            target_fresh=1,
            self_base_snapshot=observation,
            reason=_resolve_idle_reason(observation, phase),
        )

    dx = float(observation.get("err_x", 0.0)) * runtime_params.FOLLOW_CONTROL_KP_X
    dy = float(observation.get("err_y", 0.0)) * runtime_params.FOLLOW_CONTROL_KP_Y
    assistant_target = {"valid": 1, "dx": dx, "dy": dy}
    assistant_state = {
        "phase": "TRACKING",
        "selected_target": selected_target,
        "target_valid": 1,
        "target_fresh": 1,
    }
    self_base_state = _build_self_base_state(observation)
    return Decision(
        phase="TRACKING",
        selected_target=selected_target,
        self_target={"kind": "hold"},
        assistant_target=assistant_target,
        assistant_state=assistant_state,
        assistant_command=build_follow_command(
            seq=control_seq,
            valid=1,
            dx=dx,
            dy=dy,
        ),
        self_base_state=self_base_state,
    )
