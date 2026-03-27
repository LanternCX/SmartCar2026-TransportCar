"""主车视觉状态切换

@file src/master/vision_state_machine.py
"""


class VisionStateMachine:
    """根据视觉观测选择跟踪阶段和输出目标

    @brief 在搜索和跟踪之间切换主车与辅车目标
    """

    def step(self, observation=None):
        """推进一次视觉状态切换

        @brief 根据候选目标生成当前阶段和动作建议
        @param observation 当前观测字典
        @return dict
        """

        observation = {} if observation is None else dict(observation)
        candidates = tuple(observation.get("candidates", ()))
        selected_target = observation.get("target")

        # `box` 作为显式候选时优先进入跟踪输出
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
