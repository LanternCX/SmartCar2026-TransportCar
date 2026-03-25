"""@brief 视觉状态机推进与调试辅助函数."""

from vision.debug import build_transition_event
from vision.state_defs import SM
from vision.state_machine.actions import (
    handle_align_angle,
    handle_align_dist,
    handle_align_dx,
    handle_done,
    handle_orbiting,
    handle_pushing,
    handle_returning,
)
from vision.state_machine.types import VisionControlIntent, VisionStepResult


def emit_debug_event(machine, event) -> None:
    if machine._debug_sink is None:
        return
    try:
        machine._debug_sink(event)
    except Exception:
        pass


def build_debug_context(inputs, observation):
    observation_x = None
    observation_y = None
    heading_deg = None
    odom_x = None
    odom_y = None
    now_ms = None
    if observation is not None:
        observation_x = float(observation.center_x)
        observation_y = float(observation.bottom)
    if inputs is not None:
        heading_deg = float(inputs.heading_deg)
        odom_x = float(inputs.odom_x)
        odom_y = float(inputs.odom_y)
        now_ms = int(inputs.now_ms)
    return {
        "observation_x": observation_x,
        "observation_y": observation_y,
        "heading_deg": heading_deg,
        "odom_x": odom_x,
        "odom_y": odom_y,
        "now_ms": now_ms,
    }


def set_state(machine, transition, inputs, observation) -> None:
    old_state = machine.state
    machine.state = transition.state
    if old_state == machine.state:
        return
    emit_debug_event(
        machine,
        build_transition_event(
            old_state=old_state,
            transition=transition,
            stable_counter=machine._stable_counter,
            **build_debug_context(inputs, observation),
        ),
    )


def start_push(machine, odom_x: float, odom_y: float) -> None:
    machine._push_start_x = float(odom_x)
    machine._push_start_y = float(odom_y)


def reset_machine(machine) -> None:
    set_state(machine, SM.IDLE.RESET, None, None)
    machine._stable_counter = 0
    machine._push_start_x = 0.0
    machine._push_start_y = 0.0
    machine._done_since_ms = 0


def inactive_result(machine) -> VisionStepResult:
    return VisionStepResult(
        int(machine.state), VisionControlIntent(False, 0.0, 0.0, 0.0, False)
    )


def active_result(
    machine, dx_body: float, dy_body: float, d_angle_deg: float, rear_only_mode: bool
) -> VisionStepResult:
    return VisionStepResult(
        int(machine.state),
        VisionControlIntent(True, dx_body, dy_body, d_angle_deg, rear_only_mode),
    )


def step_state_machine(machine, inputs):
    observation = inputs.observation
    if (
        machine.state in (SM.ALIGN_ANGLE, SM.ALIGN_DIST, SM.ALIGN_DX)
        and observation is None
    ):
        set_state(machine, SM.IDLE.OBSERVATION_LOST, inputs, observation)
        machine._stable_counter = 0
        return inactive_result(machine)
    if machine.state == SM.IDLE:
        machine._stable_counter = 0
        if observation is None:
            return inactive_result(machine)
        set_state(machine, SM.ALIGN_ANGLE.OBSERVATION_ACQUIRED, inputs, observation)
    if machine.state == SM.ALIGN_ANGLE:
        return handle_align_angle(machine, inputs, observation)
    if machine.state == SM.ALIGN_DIST:
        return handle_align_dist(machine, inputs, observation)
    if machine.state == SM.ALIGN_DX:
        return handle_align_dx(machine, inputs, observation)
    if machine.state == SM.ORBITING:
        return handle_orbiting(machine, inputs, observation)
    if machine.state == SM.PUSHING:
        return handle_pushing(machine, inputs, observation)
    if machine.state == SM.RETURNING:
        return handle_returning(machine, inputs, observation)
    if machine.state == SM.DONE:
        return handle_done(machine, inputs, observation)
    set_state(machine, SM.IDLE.UNKNOWN_STATE_GUARD, inputs, observation)
    return inactive_result(machine)
