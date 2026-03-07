"""视觉状态机单元测试."""

from typing import Optional, Tuple

import pytest

from services.vision_protocol import VisionObservation
from services.vision_state_machine import (
    SMState,
    VisionMachineInputs,
    VisionStateConfig,
    VisionStateMachine,
)


pytestmark = pytest.mark.unit


def build_test_config(initial_state: int = SMState.IDLE) -> VisionStateMachine:
    return VisionStateMachine(
        VisionStateConfig(
            target_x_px=160.0,
            target_y_px=120.0,
            angle_kp=0.1,
            dist_kp=0.01,
            dx_kp=0.01,
            push_dx_kp=0.005,
            push_dy_m=0.12,
            push_distance_m=0.2,
            push_angle_deg=-90.0,
            angle_deadzone_px=10.0,
            angle_reentry_px=15.0,
            dist_deadzone_px=8.0,
            dx_deadzone_px=6.0,
            heading_tolerance_deg=10.0,
            stable_frames=2,
            max_dx_m=0.1,
            max_dy_m=0.12,
            max_d_angle_deg=15.0,
            done_hold_ms=200,
        ),
        initial_state=initial_state,
    )


def build_inputs(
    obs: Optional[Tuple[float, float]],
    *,
    heading_deg: float = 0.0,
    odom: Tuple[float, float] = (0.0, 0.0),
    now_ms: int = 1000,
) -> VisionMachineInputs:
    observation = None
    if obs is not None:
        observation = VisionObservation(obs[0], obs[1], now_ms)
    return VisionMachineInputs(
        observation=observation,
        heading_deg=heading_deg,
        odom_x=odom[0],
        odom_y=odom[1],
        now_ms=now_ms,
    )


def test_idle_enters_align_angle_when_observation_arrives() -> None:
    machine = build_test_config()

    result = machine.step(build_inputs((200.0, 120.0)))

    assert result.state == SMState.ALIGN_ANGLE


def test_align_angle_enters_align_dist_after_stable_centering() -> None:
    machine = build_test_config(initial_state=SMState.ALIGN_ANGLE)

    first = machine.step(build_inputs((165.0, 120.0), now_ms=1000))
    second = machine.step(build_inputs((164.0, 120.0), now_ms=1010))

    assert first.state == SMState.ALIGN_ANGLE
    assert second.state == SMState.ALIGN_DIST


def test_align_dist_returns_to_align_angle_when_x_error_grows() -> None:
    machine = build_test_config(initial_state=SMState.ALIGN_DIST)

    result = machine.step(build_inputs((200.0, 120.0)))

    assert result.state == SMState.ALIGN_ANGLE


def test_align_dx_enters_pushing_when_heading_matches_push_angle() -> None:
    machine = build_test_config(initial_state=SMState.ALIGN_DX)

    first = machine.step(build_inputs((162.0, 120.0), heading_deg=-90.0, now_ms=1000))
    second = machine.step(build_inputs((161.0, 120.0), heading_deg=-90.0, now_ms=1010))

    assert first.state == SMState.ALIGN_DX
    assert second.state == SMState.PUSHING


def test_align_dx_returns_to_align_dist_when_distance_not_ready() -> None:
    machine = build_test_config(initial_state=SMState.ALIGN_DX)

    first = machine.step(build_inputs((161.0, 150.0), heading_deg=-90.0, now_ms=1000))
    second = machine.step(build_inputs((160.0, 150.0), heading_deg=-90.0, now_ms=1010))

    assert first.state == SMState.ALIGN_DX
    assert second.state == SMState.ALIGN_DIST


def test_pushing_finishes_after_push_distance_reached() -> None:
    machine = build_test_config(initial_state=SMState.PUSHING)
    machine.start_push(0.0, 0.0)

    result = machine.step(
        build_inputs((160.0, 120.0), odom=(0.0, 0.25), heading_deg=-90.0)
    )

    assert result.state == SMState.RETURNING


def test_align_states_return_to_idle_when_target_lost() -> None:
    machine = build_test_config(initial_state=SMState.ALIGN_DX)

    result = machine.step(build_inputs(None))

    assert result.state == SMState.IDLE


def test_reset_returns_machine_to_idle() -> None:
    machine = build_test_config(initial_state=SMState.PUSHING)
    machine.start_push(1.0, 2.0)

    machine.reset()

    result = machine.step(build_inputs(None))
    assert result.state == SMState.IDLE
