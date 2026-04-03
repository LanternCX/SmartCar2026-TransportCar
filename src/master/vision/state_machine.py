"""主车视觉状态切换.

@file src/master/vision/state_machine.py
"""

import master.runtime_params as runtime_params


class MarkerStateMachine:
    def __init__(self, deadzone_px=None):
        if deadzone_px is None:
            deadzone_px = runtime_params.FOLLOW_CENTER_DEADZONE_PX
        self.deadzone_px = float(deadzone_px)

    def step(
        self,
        valid=0,
        err_x=0.0,
        err_y=0.0,
        has_target=None,
        has_new_input=None,
    ):
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
