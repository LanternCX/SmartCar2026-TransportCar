"""视觉状态机单元测试."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast

import pytest

from vision.debug import format_transition_event
from vision.protocol import VisionFrame, VisionObservation
from vision.runtime import VisionRuntime
from vision.state_defs import SM, SMState, VisionTransitionReason
from vision.state_machine import (
    VisionMachineInputs,
    VisionStateConfig,
    VisionStateMachine,
)
from vision.transforms import select_state_machine_input


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


def build_detection(
    category: str,
    left: float,
    top: float,
    right: float,
    bottom: float,
    *,
    camera_id: str = "cam_a",
    frame_id: str = "11",
    now_ms: int = 1000,
) -> VisionObservation:
    return VisionObservation(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        timestamp_ms=now_ms,
        camera_id=camera_id,
        frame_id=frame_id,
        category=category,
    )


def build_frame(
    *detections: VisionObservation, camera_id: str = "cam_a"
) -> VisionFrame:
    return VisionFrame(
        camera_id=camera_id, frame_id="11", detections=detections, timestamp_ms=1000
    )


def build_camera_frames(*frames: VisionFrame) -> Dict[str, VisionFrame]:
    """按相机 ID 构造物理相机帧映射."""
    return {frame.camera_id: frame for frame in frames}


def test_vision_runtime_keeps_fixed_camera_slots_not_camera_frames_owner() -> None:
    runtime = VisionRuntime(timeout_ms=200)

    assert runtime.get_slot("cam_a") is runtime.cam_a
    assert runtime.get_slot("cam_b") is runtime.cam_b
    assert hasattr(runtime, "camera_frames") is False


def test_idle_enters_align_angle_when_observation_arrives() -> None:
    machine = build_test_config()

    result = machine.step(build_inputs((180.0, 40.0, 220.0, 120.0)))

    assert result.state == SMState.ALIGN_ANGLE


def test_state_machine_consumes_selected_follower_or_cargo_target_only() -> None:
    cargo_frame = build_frame(
        build_detection("cargo", 90.0, 20.0, 130.0, 100.0),
        build_detection("follower", 150.0, 25.0, 190.0, 160.0),
    )

    follower_selected = select_state_machine_input(
        cargo_frame=cargo_frame,
        obstacle_frame=None,
        preferred_role="follower",
    )
    cargo_selected = select_state_machine_input(
        cargo_frame=cargo_frame,
        obstacle_frame=None,
        preferred_role="cargo",
    )

    assert follower_selected.target_role == "follower"
    assert follower_selected.observation is not None
    assert follower_selected.observation.category == "follower"
    assert cargo_selected.target_role == "cargo"
    assert cargo_selected.observation is not None
    assert cargo_selected.observation.category == "cargo"


def test_active_target_role_missing_does_not_fall_back_to_other_detection() -> None:
    cargo_frame = build_frame(build_detection("cargo", 90.0, 20.0, 130.0, 100.0))

    selected = select_state_machine_input(
        cargo_frame=cargo_frame,
        obstacle_frame=None,
        active_target_role="follower",
    )

    assert selected.target_role == "follower"
    assert selected.observation is None


def test_select_state_machine_input_accepts_runtime_without_camera_frames_dict() -> (
    None
):
    runtime = VisionRuntime(timeout_ms=200)

    selected = cast(Any, select_state_machine_input)(runtime=runtime)

    assert selected.observation is None


def test_select_state_machine_input_accepts_fixed_slots_and_keeps_camera_priority() -> (
    None
):
    runtime = VisionRuntime(timeout_ms=200)
    cast(Any, runtime.cam_a).frame = build_frame(
        build_detection(
            "follower", 140.0, 20.0, 180.0, 170.0, camera_id="cam_a", frame_id="51"
        ),
        camera_id="cam_a",
    )
    cast(Any, runtime.cam_b).frame = build_frame(
        build_detection(
            "follower", 100.0, 10.0, 220.0, 230.0, camera_id="cam_b", frame_id="52"
        ),
        camera_id="cam_b",
    )

    selected = cast(Any, select_state_machine_input)(
        runtime=runtime,
        role_camera_priorities={
            "follower": ("cam_a", "cam_b"),
            "cargo": ("cam_a", "cam_b"),
        },
    )

    assert selected.target_role == "follower"
    assert selected.observation is not None
    assert selected.observation.camera_id == "cam_a"
    assert selected.observation.bottom == 170.0


def test_select_state_machine_input_prefers_active_role_across_multiple_camera_frames() -> (
    None
):
    cam_a_frame = build_frame(
        build_detection(
            "follower", 150.0, 25.0, 190.0, 160.0, camera_id="cam_a", frame_id="31"
        ),
        camera_id="cam_a",
    )
    cam_b_frame = build_frame(
        build_detection(
            "cargo", 90.0, 20.0, 130.0, 210.0, camera_id="cam_b", frame_id="32"
        ),
        camera_id="cam_b",
    )

    selected = cast(Any, select_state_machine_input)(
        camera_frames=build_camera_frames(cam_a_frame, cam_b_frame),
        active_target_role="cargo",
        role_camera_priorities={
            "follower": ("cam_a", "cam_b"),
            "cargo": ("cam_a", "cam_b"),
            "obstacle": ("cam_b", "cam_a"),
        },
    )

    assert selected.target_role == "cargo"
    assert selected.observation is not None
    assert selected.observation.category == "cargo"
    assert selected.observation.camera_id == "cam_b"


def test_overlapping_category_from_two_cameras_uses_priority_camera_before_score_tie_break() -> (
    None
):
    cam_a_frame = build_frame(
        build_detection(
            "follower", 140.0, 20.0, 180.0, 170.0, camera_id="cam_a", frame_id="41"
        ),
        camera_id="cam_a",
    )
    cam_b_frame = build_frame(
        build_detection(
            "follower", 100.0, 10.0, 220.0, 230.0, camera_id="cam_b", frame_id="42"
        ),
        camera_id="cam_b",
    )

    selected = cast(Any, select_state_machine_input)(
        camera_frames=build_camera_frames(cam_a_frame, cam_b_frame),
        role_camera_priorities={
            "follower": ("cam_a", "cam_b"),
            "cargo": ("cam_a", "cam_b"),
        },
    )

    assert selected.target_role == "follower"
    assert selected.observation is not None
    assert selected.observation.camera_id == "cam_a"
    assert selected.observation.bottom == 170.0


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
    source = Path("src/vision/state_machine/__init__.py").read_text(encoding="utf-8")
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "typing":
            raise ImportError("no module named 'typing'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    namespace = {"__name__": "vision_state_machine_probe"}
    exec(compile(source, "vision/state_machine/__init__.py", "exec"), namespace)

    assert "VisionStateMachine" in namespace
