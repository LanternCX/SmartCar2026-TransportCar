"""主车视觉状态切换.

@file src/master/vision/state_machine.py
"""

_package_name = str(globals().get("__package__", ""))

if "." in _package_name:
    from .. import runtime_params
else:
    import runtime_params


class MarkerStateMachine:
    """主车视觉阶段切换器

    @brief 这里只根据目标可见性和死区切换阶段, 不持有跨周期底座状态, 也不生成控制输出
    """

    def __init__(self, deadzone_px=None):
        if deadzone_px is None:
            deadzone_px = runtime_params.FOLLOW_CENTER_DEADZONE_PX
        self.deadzone_px = float(deadzone_px)
        self.phase = "MARKER_MISSING"

    def step(
        self,
        valid=0,
        err_x=0.0,
        err_y=0.0,
        has_target=None,
        has_new_input=None,
    ):
        """根据目标可见性与偏差决定当前视觉阶段.

        @brief 这里只维护 `MARKER_MISSING/CENTER_HOLD/ALIGN_X/ALIGN_Y` 四态, 让决策层按阶段选择动作。
        """

        _ = has_new_input
        if has_target is None:
            has_target = int(valid) == 1
        err_x = float(err_x)
        err_y = float(err_y)
        if not has_target:
            self.phase = "MARKER_MISSING"
            return {"phase": self.phase, "hold": True}
        if abs(err_x) <= self.deadzone_px and abs(err_y) <= self.deadzone_px:
            self.phase = "CENTER_HOLD"
            return {"phase": self.phase, "hold": True}
        if abs(err_x) > self.deadzone_px:
            self.phase = "ALIGN_X"
            return {"phase": self.phase, "hold": False}
        self.phase = "ALIGN_Y"
        return {"phase": self.phase, "hold": False}


VisionStateMachine = MarkerStateMachine
