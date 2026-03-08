"""视觉相对控制意图转换单元测试."""

import pytest

from services.vision_state_machine import VisionControlIntent, resolve_relative_intent


pytestmark = pytest.mark.unit


def test_relative_intent_converts_to_absolute_targets() -> None:
    intent = VisionControlIntent(
        active=True,
        dx_body=1.0,
        dy_body=0.0,
        d_angle_deg=15.0,
        rear_only_mode=False,
    )

    target = resolve_relative_intent(intent, odom_x=2.0, odom_y=3.0, heading_deg=90.0)

    assert target is not None
    assert round(target.x, 6) == 2.0
    assert round(target.y, 6) == 4.0
    assert target.angle_deg == 105.0


def test_inactive_intent_returns_none() -> None:
    intent = VisionControlIntent(
        active=False,
        dx_body=0.0,
        dy_body=0.0,
        d_angle_deg=0.0,
        rear_only_mode=False,
    )

    assert (
        resolve_relative_intent(intent, odom_x=0.0, odom_y=0.0, heading_deg=0.0) is None
    )
