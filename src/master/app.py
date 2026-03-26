"""主车最小应用定义

@file src/master/app.py
"""

from master.decision import decide_from_observation
from master.motion_runtime import MotionRuntime
from master.vision_ingress import VisionIngress
from master.vision_state_machine import VisionStateMachine


class MasterApp:
    """主车最小应用壳

    @brief 为后续主车运行时预留最小入口
    """

    def __init__(self, vision_uart="uart6", camera_ids=("cam_a", "cam_b")):
        self.ingress = VisionIngress(vision_uart=vision_uart, camera_ids=camera_ids)
        self.state_machine = VisionStateMachine()
        self.motion_runtime = MotionRuntime()
        self.last_assistant_command = "HOLD"

    def step(self, observation=None):
        """推进一次主车最小流程

        @brief 串联视觉状态机、最小决策和主车运动输出
        @param observation 当前观测字典
        @return dict
        """

        prepared_observation = self.ingress.prepare_observation(observation)
        decision = decide_from_observation(
            prepared_observation, state_machine=self.state_machine
        )
        self_target = self.motion_runtime.apply_self_target(decision.self_target)
        self.last_assistant_command = decision.assistant_command
        return {
            "selected_target": decision.selected_target,
            "phase": decision.phase,
            "poll_request": prepared_observation.get("poll_request"),
            "self_target": self_target,
            "assistant_command": self.last_assistant_command,
        }
