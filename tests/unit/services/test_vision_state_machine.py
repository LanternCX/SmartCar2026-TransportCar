"""视觉状态机单元测试."""

from pathlib import Path
from typing import Optional, Tuple

import pytest

from vision.debug import format_transition_event
from vision.protocol import VisionObservation
from vision.state_defs import SM, SMState, VisionTransitionReason
from vision.state_machine import (
    VisionMachineInputs,
    VisionStateConfig,
    VisionStateMachine,
)


pytestmark = pytest.mark.unit


def build_test_config(initial_state=SM.IDLE) -> VisionStateMachine:
    return VisionStateMachine(
        VisionStateConfig(
            target_center_x_px=160.0,
            target_bottom_px=240.0,
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
    obs: Optional[Tuple[float, float, float, float]],
    *,
    heading_deg: float = 0.0,
    odom: Tuple[float, float] = (0.0, 0.0),
    now_ms: int = 1000,
) -> VisionMachineInputs:
    observation = None
    if obs is not None:
        observation = VisionObservation(obs[0], obs[1], obs[2], obs[3], now_ms)
    return VisionMachineInputs(
        observation=observation,
        heading_deg=heading_deg,
        odom_x=odom[0],
        odom_y=odom[1],
        now_ms=now_ms,
    )


def test_idle_enters_align_angle_when_observation_arrives() -> None:
    machine = build_test_config()

    result = machine.step(build_inputs((180.0, 40.0, 220.0, 120.0)))

    assert result.state == SMState.ALIGN_ANGLE


def test_align_angle_uses_box_center_x_not_left_edge() -> None:
    machine = build_test_config(initial_state=SM.ALIGN_ANGLE)

    result = machine.step(build_inputs((130.0, 20.0, 190.0, 90.0)))

    assert result.intent.active is False
    assert result.intent.d_angle_deg == 0.0


def test_align_angle_enters_align_dist_after_stable_centering() -> None:
    machine = build_test_config(initial_state=SM.ALIGN_ANGLE)

    first = machine.step(build_inputs((145.0, 20.0, 175.0, 240.0), now_ms=1000))
    second = machine.step(build_inputs((146.0, 20.0, 174.0, 240.0), now_ms=1010))

    assert first.state == SMState.ALIGN_ANGLE
    assert second.state == SMState.ALIGN_DIST


def test_align_dist_returns_to_align_angle_when_center_error_grows() -> None:
    machine = build_test_config(initial_state=SM.ALIGN_DIST)

    result = machine.step(build_inputs((180.0, 20.0, 220.0, 240.0)))

    assert result.state == SMState.ALIGN_ANGLE


def test_align_dist_moves_forward_when_box_bottom_is_above_target() -> None:
    machine = build_test_config(initial_state=SM.ALIGN_DIST)

    result = machine.step(build_inputs((145.0, 20.0, 175.0, 210.0)))

    assert result.intent.active is True
    assert result.intent.dy_body > 0.0


def test_align_dx_enters_pushing_when_heading_matches_push_angle() -> None:
    machine = build_test_config(initial_state=SM.ALIGN_DX)

    first = machine.step(
        build_inputs((156.0, 170.0, 164.0, 240.0), heading_deg=-90.0, now_ms=1000)
    )
    second = machine.step(
        build_inputs((157.0, 170.0, 163.0, 240.0), heading_deg=-90.0, now_ms=1010)
    )

    assert first.state == SMState.ALIGN_DX
    assert second.state == SMState.PUSHING


def test_orbiting_requests_rear_mode_while_heading_not_ready() -> None:
    machine = build_test_config(initial_state=SM.ORBITING)

    result = machine.step(
        build_inputs((156.0, 170.0, 164.0, 240.0), heading_deg=0.0, now_ms=1000)
    )

    assert result.intent.active is True
    assert result.intent.rear_only_mode is True
    assert result.intent.d_angle_deg < 0.0


def test_align_dx_returns_to_align_dist_when_distance_not_ready() -> None:
    machine = build_test_config(initial_state=SM.ALIGN_DX)

    first = machine.step(
        build_inputs((156.0, 140.0, 164.0, 210.0), heading_deg=-90.0, now_ms=1000)
    )
    second = machine.step(
        build_inputs((157.0, 140.0, 163.0, 210.0), heading_deg=-90.0, now_ms=1010)
    )

    assert first.state == SMState.ALIGN_DX
    assert second.state == SMState.ALIGN_DIST


def test_pushing_finishes_after_push_distance_reached() -> None:
    machine = build_test_config(initial_state=SM.PUSHING)
    machine.start_push(0.0, 0.0)

    result = machine.step(
        build_inputs((145.0, 20.0, 175.0, 240.0), odom=(0.0, 0.25), heading_deg=-90.0)
    )

    assert result.state == SMState.RETURNING


def test_align_states_return_to_idle_when_target_lost() -> None:
    machine = build_test_config(initial_state=SM.ALIGN_DX)

    result = machine.step(build_inputs(None))

    assert result.state == SMState.IDLE


def test_reset_returns_machine_to_idle() -> None:
    machine = build_test_config(initial_state=SM.PUSHING)
    machine.start_push(1.0, 2.0)

    machine.reset()

    result = machine.step(build_inputs(None))
    assert result.state == SMState.IDLE


def test_debug_logger_outputs_transition_reason() -> None:
    events = []
    machine = VisionStateMachine(
        build_test_config(initial_state=SM.ALIGN_DIST).config,
        initial_state=SM.ALIGN_DIST,
        debug_sink=events.append,
    )

    machine.step(build_inputs((180.0, 20.0, 220.0, 240.0), now_ms=1234))

    assert len(events) == 1
    assert events[0].reason == VisionTransitionReason.ANGLE_ERROR_REENTRY
    assert "VSM TRANS ALIGN_DIST->ALIGN_ANGLE" in format_transition_event(events[0])
    assert "reason=angle_error_reentry" in format_transition_event(events[0])
    assert "now=1234" in format_transition_event(events[0])


def test_set_state_accepts_wrapped_transition_spec() -> None:
    events = []
    machine = VisionStateMachine(
        build_test_config(initial_state=SM.ALIGN_DX).config,
        initial_state=SM.ALIGN_DX,
        debug_sink=events.append,
    )

    machine._set_state(SM.DONE.RETURN_HEADING_REACHED, build_inputs(None), None)

    assert machine.state == SM.DONE
    assert events[0].transition == SM.DONE.RETURN_HEADING_REACHED
    assert format_transition_event(events[0]).startswith("VSM TRANS ALIGN_DX->DONE")


def test_module_can_load_without_typing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path("src/vision/state_machine.py").read_text(encoding="utf-8")
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "typing":
            raise ImportError("no module named 'typing'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    namespace = {"__name__": "vision_state_machine_probe"}
    exec(compile(source, "vision_state_machine.py", "exec"), namespace)

    assert "VisionStateMachine" in namespace
