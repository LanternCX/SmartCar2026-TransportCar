"""主车决策结果生成

@file src/master/decision.py
"""

from config.params import (
    FOLLOW_CONTROL_KP_ANGLE,
    FOLLOW_CONTROL_KP_X,
    FOLLOW_CONTROL_KP_Y,
)
from master.protocol import build_follow_command, build_hold_command, build_move_command


class Decision:
    """封装主车决策阶段的输出结果

    @brief 统一保存目标选择、主车目标和辅车命令
    """

    def __init__(
        self,
        phase,
        selected_target,
        self_target,
        assistant_target,
        assistant_command,
    ):
        self.phase = str(phase)
        self.selected_target = str(selected_target)
        self.self_target = dict(self_target)
        self.assistant_target = dict(assistant_target)
        self.assistant_command = str(assistant_command)


def decide_from_state(state_output):
    """根据状态机输出生成决策结果

    @brief 将状态机输出转换为主车和辅车的动作结果
    @param state_output 状态机输出字典
    @return Decision
    """

    phase = str(state_output.get("phase", "search"))
    selected_target = str(state_output.get("selected_target", "idle"))
    self_target = dict(state_output.get("self", {"kind": "hold"}))
    assistant_target = dict(state_output.get("assistant", {"kind": "hold"}))

    # 状态机输出为 move 时生成显式运动命令, 其余情况统一收口为保持命令
    if assistant_target.get("kind") == "move":
        assistant_command = build_move_command(
            assistant_target.get("dx", 0.0),
            assistant_target.get("dy", 0.0),
            assistant_target.get("dtheta", 0.0),
        )
    else:
        assistant_command = build_hold_command()
    return Decision(
        phase, selected_target, self_target, assistant_target, assistant_command
    )


def _build_idle_decision(control_seq):
    """构造无有效目标时的决策结果

    @brief 使用 `valid=0` 跟随报文通知辅车保持当前状态
    @param control_seq 当前控制序号
    @return Decision
    """

    # 空目标阶段仍然发送控制序号, 便于辅车同步当前控制拍次
    assistant_target = {"valid": 0, "dx": 0.0, "dy": 0.0, "d_angle": 0.0}
    return Decision(
        phase="follow_idle",
        selected_target="idle",
        self_target={"kind": "hold"},
        assistant_target=assistant_target,
        assistant_command=build_follow_command(
            seq=control_seq,
            valid=0,
            dx=0.0,
            dy=0.0,
            d_angle=0.0,
        ),
    )


def decide_from_observation(observation, state_machine=None):
    """根据观测生成跟随决策

    @brief 将视觉误差换算为发给辅车的跟随控制量
    @param observation 观测字典
    @return Decision
    """

    control_seq = int(observation.get("control_seq", 0))
    if int(observation.get("valid", 0)) != 1:
        return _build_idle_decision(control_seq)

    # 视觉误差按参数中的比例系数换算为辅车控制量
    dx = float(observation.get("err_x", 0.0)) * FOLLOW_CONTROL_KP_X
    dy = float(observation.get("err_y", 0.0)) * FOLLOW_CONTROL_KP_Y
    d_angle = float(observation.get("d_angle", 0.0)) * FOLLOW_CONTROL_KP_ANGLE
    assistant_target = {"valid": 1, "dx": dx, "dy": dy, "d_angle": d_angle}
    return Decision(
        phase="follow_track",
        selected_target=str(observation.get("target", "idle")),
        self_target={"kind": "hold"},
        assistant_target=assistant_target,
        assistant_command=build_follow_command(
            seq=control_seq,
            valid=1,
            dx=dx,
            dy=dy,
            d_angle=d_angle,
        ),
    )
