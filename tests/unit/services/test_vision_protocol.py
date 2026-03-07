"""视觉协议解析单元测试."""

import pytest

from services.vision_protocol import VisionObservation, VisionProtocol


pytestmark = pytest.mark.unit


def test_parse_xy_packet_from_uart6() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("x=123,y=45", source="uart6", now_ms=1000)

    assert isinstance(parsed, VisionObservation)
    assert parsed.x == 123.0
    assert parsed.y == 45.0
    assert parsed.timestamp_ms == 1000


def test_reject_non_visual_packet() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "x=1,y=2,angle=3", source="uart6", now_ms=1000
    )

    assert parsed is None


def test_reject_packet_from_non_visual_source() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("x=123,y=45", source="uart3", now_ms=1000)

    assert parsed is None


def test_observation_timeout_marks_target_lost() -> None:
    protocol = VisionProtocol(timeout_ms=200)
    protocol.try_parse_observation("x=123,y=45", source="uart6", now_ms=1000)

    active = protocol.get_observation(now_ms=1199)
    expired = protocol.get_observation(now_ms=1201)

    assert active is not None
    assert expired is None


def test_clear_drops_cached_observation() -> None:
    protocol = VisionProtocol(timeout_ms=200)
    protocol.try_parse_observation("x=123,y=45", source="uart6", now_ms=1000)

    protocol.clear()

    assert protocol.get_observation(now_ms=1000) is None
