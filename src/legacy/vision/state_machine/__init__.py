"""@brief 视觉状态机公开入口与 facade."""

from vision.state_defs import SM
from vision.state_machine.core import (
    active_result,
    build_debug_context,
    emit_debug_event,
    inactive_result,
    reset_machine,
    set_state,
    start_push,
    step_state_machine,
)
from vision.state_machine.types import (
    VisionControlIntent,
    VisionMachineInputs,
    VisionStateConfig,
    VisionStepResult,
)
from vision.state_registry import vision_state_registry


class VisionStateMachine:
    """@brief 将视觉观测映射为相对位置式控制意图的状态机."""

    def __init__(
        self, config: VisionStateConfig, initial_state=SM.IDLE, debug_sink=None
    ):
        self.config = config
        coerced_state = vision_state_registry.coerce_state(initial_state)
        self.state = coerced_state if coerced_state is not None else SM.IDLE
        self._debug_sink = debug_sink
        self._stable_counter = 0
        self._push_start_x = 0.0
        self._push_start_y = 0.0
        self._done_since_ms = 0

    _emit_debug_event = emit_debug_event
    _build_debug_context = staticmethod(build_debug_context)
    _set_state = set_state
    start_push = start_push
    reset = reset_machine
    _inactive_result = inactive_result
    _active_result = active_result

    def step(self, inputs: VisionMachineInputs) -> VisionStepResult:
        return step_state_machine(self, inputs)


__all__ = (
    "VisionStateConfig",
    "VisionMachineInputs",
    "VisionControlIntent",
    "VisionStepResult",
    "VisionStateMachine",
)
