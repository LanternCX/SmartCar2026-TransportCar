"""视觉状态注册表单元测试."""

import pytest

from vision.state_defs import SM, SMState, VisionTransitionReason
from vision.state_registry import vision_state_registry


pytestmark = pytest.mark.unit


def test_registry_returns_registered_state_name() -> None:
    assert vision_state_registry.get_state_name(SMState.ALIGN_DX) == "ALIGN_DX"


def test_registry_returns_registered_reason_name() -> None:
    assert (
        vision_state_registry.get_reason_name(
            VisionTransitionReason.ANGLE_ERROR_REENTRY
        )
        == "angle_error_reentry"
    )


def test_registry_accepts_wrapped_state_object() -> None:
    assert vision_state_registry.get_state_name(SM.ALIGN_DX) == "ALIGN_DX"


def test_wrapped_state_exposes_transition_metadata() -> None:
    transition = SM.DONE.RETURN_HEADING_REACHED
    assert transition is not None

    assert transition.state == SM.DONE
    assert transition.reason == VisionTransitionReason.RETURN_HEADING_REACHED
