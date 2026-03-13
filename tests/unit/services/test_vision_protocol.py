"""视觉协议解析单元测试."""

import pytest

from vision.protocol import VisionObservation, VisionProtocol


pytestmark = pytest.mark.unit


def test_parse_bbox_packet_from_uart6() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "left=100,top=20,right=140,bottom=90", source="uart6", now_ms=1000
    )

    assert parsed.consumed is True
    assert isinstance(parsed.observation, VisionObservation)
    assert parsed.observation.left == 100.0
    assert parsed.observation.top == 20.0
    assert parsed.observation.right == 140.0
    assert parsed.observation.bottom == 90.0
    assert parsed.observation.center_x == 120.0
    assert parsed.observation.center_y == 55.0
    assert parsed.observation.width == 40.0
    assert parsed.observation.height == 70.0
    assert parsed.observation.timestamp_ms == 1000


def test_bbox_field_order_does_not_change_visual_consumption_priority() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "bottom=90,right=140,top=20,left=100", source="uart6", now_ms=1000
    )

    assert parsed.consumed is True
    assert parsed.observation is not None
    assert parsed.observation.left == 100.0
    assert parsed.observation.bottom == 90.0


def test_legacy_xy_packet_is_consumed_without_caching_observation() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("x=123,y=45", source="uart6", now_ms=1000)

    assert parsed.consumed is True
    assert parsed.observation is None
    assert protocol.get_observation(now_ms=1000) is None


def test_incomplete_bbox_packet_is_consumed_without_caching_observation() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "left=1,top=2,right=3", source="uart6", now_ms=1000
    )

    assert parsed.consumed is True
    assert parsed.observation is None


def test_mixed_legacy_visual_payload_is_consumed_without_caching_observation() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "x=120,y=80,angle=0", source="uart6", now_ms=1000
    )

    assert parsed.consumed is True
    assert parsed.observation is None


def test_malformed_legacy_visual_payload_is_consumed_without_caching_observation() -> (
    None
):
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("x=1,y=bad", source="uart6", now_ms=1000)

    assert parsed.consumed is True
    assert parsed.observation is None


def test_non_visual_packet_from_uart6_falls_back_to_command_router() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("vx=1", source="uart6", now_ms=1000)

    assert parsed.consumed is False
    assert parsed.observation is None


def test_reject_packet_from_non_visual_source() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "left=100,top=20,right=140,bottom=90", source="uart3", now_ms=1000
    )

    assert parsed.consumed is False
    assert parsed.observation is None


def test_observation_timeout_marks_target_lost() -> None:
    protocol = VisionProtocol(timeout_ms=200)
    protocol.try_parse_observation(
        "left=100,top=20,right=140,bottom=90", source="uart6", now_ms=1000
    )

    active = protocol.get_observation(now_ms=1199)
    expired = protocol.get_observation(now_ms=1201)

    assert active is not None
    assert expired is None


def test_clear_drops_cached_observation() -> None:
    protocol = VisionProtocol(timeout_ms=200)
    protocol.try_parse_observation(
        "left=100,top=20,right=140,bottom=90", source="uart6", now_ms=1000
    )

    protocol.clear()

    assert protocol.get_observation(now_ms=1000) is None


def test_shift_latest_timestamp_extends_observation_lifetime() -> None:
    protocol = VisionProtocol(timeout_ms=200)
    protocol.try_parse_observation(
        "left=100,top=20,right=140,bottom=90", source="uart6", now_ms=1000
    )

    protocol.shift_latest_timestamp(500)

    active = protocol.get_observation(now_ms=1600)

    assert active is not None
    assert active.timestamp_ms == 1500
