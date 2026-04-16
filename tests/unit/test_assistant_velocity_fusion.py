"""辅车速度融合与最小状态测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.assistant.control_protocol_input import VelocityControl
from vision.assistant.vision_input import VisionObservation
from vision.assistant.velocity_fusion import (
    STATE_FAULT_STOP,
    STATE_IDLE,
    STATE_TRACKING,
    STATE_VISION_ONLY,
    VelocityFusion,
)


def test_tracking_merges_control_rhythm_with_vision_correction() -> None:
    fusion = VelocityFusion(output_limit=10.0, degraded_output_limit=3.0)
    control = VelocityControl(vx=4.0, vy=5.0, omega=6.0, timestamp_ms=100)
    vision = VisionObservation(x=-1.5, y=2.5, timestamp_ms=101)

    result = fusion.fuse(control=control, vision=vision)

    assert result.state == STATE_TRACKING
    assert (result.vx, result.vy, result.omega) == (2.5, 7.5, 6.0)
    assert result.control_contribution == {"vx": 4.0, "vy": 5.0, "omega": 6.0}
    assert result.vision_contribution == {"vx": -1.5, "vy": 2.5, "omega": 0.0}


def test_tracking_applies_unified_output_limit() -> None:
    fusion = VelocityFusion(output_limit=10.0, degraded_output_limit=3.0)
    control = VelocityControl(vx=8.0, vy=9.0, omega=12.0, timestamp_ms=100)
    vision = VisionObservation(x=5.0, y=-30.0, timestamp_ms=101)

    result = fusion.fuse(control=control, vision=vision)

    assert result.state == STATE_TRACKING
    assert (result.vx, result.vy, result.omega) == (10.0, -10.0, 10.0)


def test_vision_only_uses_tighter_limit_and_zero_omega() -> None:
    fusion = VelocityFusion(output_limit=10.0, degraded_output_limit=3.0)
    vision = VisionObservation(x=8.0, y=-5.0, timestamp_ms=101)

    result = fusion.fuse(control=None, vision=vision)

    assert result.state == STATE_VISION_ONLY
    assert (result.vx, result.vy, result.omega) == (3.0, -3.0, 0.0)
    assert result.control_contribution == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert result.vision_contribution == {"vx": 8.0, "vy": -5.0, "omega": 0.0}


def test_fault_stop_outputs_zero_when_vision_is_missing() -> None:
    fusion = VelocityFusion(output_limit=10.0, degraded_output_limit=3.0)
    control = VelocityControl(vx=4.0, vy=5.0, omega=6.0, timestamp_ms=100)

    result = fusion.fuse(control=control, vision=None)

    assert result.state == STATE_FAULT_STOP
    assert (result.vx, result.vy, result.omega) == (0.0, 0.0, 0.0)


def test_idle_outputs_zero_when_both_inputs_are_missing() -> None:
    fusion = VelocityFusion(output_limit=10.0, degraded_output_limit=3.0)

    result = fusion.fuse(control=None, vision=None)

    assert result.state == STATE_IDLE
    assert (result.vx, result.vy, result.omega) == (0.0, 0.0, 0.0)
    assert result.control_contribution == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert result.vision_contribution == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
