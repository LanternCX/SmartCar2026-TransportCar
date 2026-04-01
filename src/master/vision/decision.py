"""主车二维控制决策.

@file src/master/vision/decision.py
"""

from master.protocol import build_follow_command
import master.runtime_params as runtime_params


class Decision:
    def __init__(
        self,
        phase,
        selected_target,
        self_target,
        assistant_target,
        assistant_state,
        assistant_command,
    ):
        self.phase = str(phase)
        self.selected_target = str(selected_target)
        self.self_target = dict(self_target)
        self.assistant_target = dict(assistant_target)
        self.assistant_state = dict(assistant_state)
        self.assistant_command = str(assistant_command)


def decide_from_state(state_output):
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
):
    assistant_target = {"valid": 0, "dx": 0.0, "dy": 0.0}
    assistant_state = {
        "phase": phase,
        "selected_target": selected_target,
        "target_valid": int(target_valid),
        "target_fresh": int(target_fresh),
    }
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
        ),
    )


def decide_from_observation(observation, state_machine=None):
    _ = state_machine
    control_seq = int(observation.get("control_seq", 0))
    phase = str(observation.get("phase", "MARKER_MISSING"))
    selected_target = str(
        observation.get("selected_target", observation.get("target", "idle"))
    )
    if int(observation.get("valid", 0)) != 1:
        return _build_idle_decision(
            control_seq,
            phase=phase,
            selected_target=selected_target,
        )
    if int(observation.get("fresh", 1)) != 1 or int(observation.get("stale", 0)) == 1:
        return _build_idle_decision(
            control_seq,
            phase=phase,
            selected_target=selected_target,
        )
    if phase != "TRACKING":
        return _build_idle_decision(
            control_seq,
            phase=phase,
            selected_target=selected_target,
            target_valid=1,
            target_fresh=1,
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
    )
