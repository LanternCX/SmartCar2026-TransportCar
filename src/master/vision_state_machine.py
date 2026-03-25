"""主车简化视觉状态机.

@file src/master/vision_state_machine.py
"""


class VisionStateMachine:
    """主车最小视觉状态机

    @brief 只保留搜索与跟踪两种最小阶段
    """

    def step(self, observation=None) -> dict:
        """推进一次最小视觉状态机

        @brief 有目标时进入 tracking, 无目标时进入 search
        @param observation 当前观测字典
        @return dict
        """

        observation = {} if observation is None else dict(observation)
        candidates = tuple(observation.get("candidates", ()))
        selected_target = observation.get("target")
        if "box" in candidates:
            selected_target = "box"
        if selected_target is None:
            return {
                "phase": "search",
                "selected_target": "idle",
                "self": {"kind": "hold"},
                "assistant": {"kind": "hold"},
            }
        return {
            "phase": "tracking",
            "selected_target": str(selected_target),
            "self": {
                "kind": "move",
                "vx": float(observation.get("offset_x", 0.0)),
                "vy": float(observation.get("forward", 0.0)),
                "omega": 0.0,
            },
            "assistant": {
                "kind": "move",
                "dx": float(observation.get("assistant_dx", 0.0)),
                "dy": float(observation.get("assistant_dy", 0.0)),
                "dtheta": float(observation.get("assistant_dtheta", 0.0)),
            },
        }
