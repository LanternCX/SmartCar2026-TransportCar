"""主车最小决策输出.

@file src/master/decision.py
"""

from master.protocol import build_hold_command, build_move_command
from master.vision_state_machine import VisionStateMachine


class Decision:
    """主车最小决策结果

    @brief 统一收口目标选择、自身目标和辅车命令
    """

    def __init__(
        self,
        phase: str,
        selected_target: str,
        self_target: dict,
        assistant_target: dict,
        assistant_command: str,
    ) -> None:
        self.phase = str(phase)
        self.selected_target = str(selected_target)
        self.self_target = dict(self_target)
        self.assistant_target = dict(assistant_target)
        self.assistant_command = str(assistant_command)


def decide_from_state(state_output: dict) -> Decision:
    """根据状态机输出生成最小决策

    @brief 把目标选择和动作输出收口为统一决策对象
    @param state_output 状态机输出字典
    @return Decision
    """

    phase = str(state_output.get("phase", "search"))
    selected_target = str(state_output.get("selected_target", "idle"))
    self_target = dict(state_output.get("self", {"kind": "hold"}))
    assistant_target = dict(state_output.get("assistant", {"kind": "hold"}))
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


def decide_from_observation(observation, state_machine=None) -> Decision:
    """根据观测生成最小决策

    @brief 优先选择 box, 否则回退到当前 target, 全缺失时保持
    @param observation 观测字典
    @return Decision
    """

    machine = VisionStateMachine() if state_machine is None else state_machine
    state_output = machine.step(observation)
    return decide_from_state(state_output)
