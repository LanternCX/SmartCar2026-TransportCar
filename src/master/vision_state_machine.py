"""主车视觉状态切换

@file src/master/vision_state_machine.py
"""


class MarkerStateMachine:
    """最小色标状态机.

    @brief 只维护丢失、跟踪和居中保持三个阶段。
    """

    def __init__(self, deadzone_px=8.0):
        self.deadzone_px = float(deadzone_px)

    def step(
        self,
        valid=0,
        err_x=0.0,
        err_y=0.0,
        has_target=None,
        has_new_input=None,
    ):
        """根据当前误差推进阶段.

        @brief 状态机只根据当前是否仍有目标和误差大小判断阶段。
        @param valid 兼容旧接口的目标有效标记
        @param err_x 横向误差
        @param err_y 纵向误差
        @return dict
        """

        _ = has_new_input
        if has_target is None:
            has_target = int(valid) == 1
        if not has_target:
            return {"phase": "MARKER_MISSING", "hold": True}
        if (
            abs(float(err_x)) <= self.deadzone_px
            and abs(float(err_y)) <= self.deadzone_px
        ):
            return {"phase": "CENTER_HOLD", "hold": True}
        return {"phase": "TRACKING", "hold": False}


VisionStateMachine = MarkerStateMachine
