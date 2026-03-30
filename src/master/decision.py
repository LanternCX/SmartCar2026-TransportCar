"""主车决策结果生成

@file src/master/decision.py
"""

from config.params import FOLLOW_CONTROL_KP_X, FOLLOW_CONTROL_KP_Y
from master.protocol import build_follow_command


class Decision:
    """封装主车决策阶段的输出结果.

    @brief 统一保存目标选择、主车目标和辅车命令。
    """

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
    """根据状态机输出生成决策结果.

    @brief 当前阶段主车保持不动, 辅车默认发送零位移跟随命令。
    @param state_output 状态机输出字典
    @return Decision
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
):
    """构造无有效位移输出时的决策结果.

    @brief 使用 `valid=0` 跟随报文通知辅车保持当前状态。
    @param control_seq 当前控制序号
    @param phase 当前阶段名
    @param selected_target 当前选中的目标名
    @return Decision
    """

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
    """根据观测生成跟随决策.

    @brief 当前阶段只把视觉误差映射为辅车二维位移命令。
    @param observation 观测字典
    @return Decision
    """

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

    dx = float(observation.get("err_x", 0.0)) * FOLLOW_CONTROL_KP_X
    dy = float(observation.get("err_y", 0.0)) * FOLLOW_CONTROL_KP_Y
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
