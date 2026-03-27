"""主车最小应用定义

@file src/master/app.py
"""

from master.decision import decide_from_observation
from master.motion_runtime import MotionRuntime
from master.vision_ingress import VisionIngress


class MasterApp:
    """主车最小应用壳

    @brief 为后续主车运行时预留最小入口
    """

    def __init__(self, active_uart="uart6", reserved_uarts=("uart8",)):
        self.ingress = VisionIngress(
            active_uart=active_uart,
            reserved_uarts=reserved_uarts,
        )
        self.motion_runtime = MotionRuntime()
        self.last_assistant_command = ""
        self.last_result = {
            "selected_target": "idle",
            "phase": "follow_idle",
            "active_uart": active_uart,
            "reserved_uarts": tuple(reserved_uarts),
            "self_target": {"kind": "hold"},
            "assistant_command": "",
        }

    def step(self, observation=None):
        """推进一次主车最小流程

        @brief 串联视觉状态机、最小决策和主车运动输出
        @param observation 当前观测字典
        @return dict
        """

        prepared_observation = self.ingress.prepare_observation(observation)
        if prepared_observation.get("source_status") != "active":
            return dict(self.last_result)
        prepared_observation["control_seq"] = self.motion_runtime.next_control_seq()
        decision = decide_from_observation(prepared_observation)
        self_target = self.motion_runtime.apply_self_target(decision.self_target)
        self.last_assistant_command = decision.assistant_command
        self.last_result = {
            "selected_target": decision.selected_target,
            "phase": decision.phase,
            "active_uart": prepared_observation.get("active_uart"),
            "reserved_uarts": prepared_observation.get("reserved_uarts"),
            "self_target": self_target,
            "assistant_command": self.last_assistant_command,
        }
        return dict(self.last_result)
