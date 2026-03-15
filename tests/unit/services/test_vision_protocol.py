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


def test_single_query_can_return_multiple_detection_messages_for_one_frame() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    first = protocol.try_parse_observation(
        "camera_id=front,frame_id=12,category=cargo,left=100,top=20,right=140,bottom=90",
        source="uart6",
        now_ms=1000,
    )
    second = protocol.try_parse_observation(
        "camera_id=front,frame_id=12,category=follower,left=150,top=25,right=190,bottom=95",
        source="uart6",
        now_ms=1001,
    )
    end = protocol.try_parse_observation(
        "camera_id=front,frame_id=12,frame_end=1",
        source="uart6",
        now_ms=1002,
    )

    assert first.consumed is True
    assert second.consumed is True
    assert end.consumed is True
    frame = protocol.get_frame(now_ms=1002)
    assert frame is not None
    assert frame.camera_id == "front"
    assert frame.frame_id == "12"
    assert [d.category for d in frame.detections] == ["cargo", "follower"]
    assert frame.detections[0].left == 100.0
    assert frame.detections[1].right == 190.0
    latest = protocol.get_observation(now_ms=1002)
    assert latest is not None
    assert latest.camera_id == "front"
    assert latest.frame_id == "12"
    assert latest.category == "follower"


def test_protocol_requires_explicit_frame_end_marker() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "camera_id=front,frame_id=21,category=cargo,left=100,top=20,right=140,bottom=90",
        source="uart6",
        now_ms=1000,
    )

    assert parsed.consumed is True
    assert parsed.observation is not None
    assert protocol.get_frame(now_ms=1000) is None
    assert protocol.get_observation(now_ms=1000) is None


def test_explicit_frame_end_commits_empty_frame() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "camera_id=front,frame_id=13,frame_end=1",
        source="uart6",
        now_ms=1000,
    )

    assert parsed.consumed is True
    assert parsed.observation is None
    frame = protocol.get_frame(now_ms=1000)
    assert frame is not None
    assert frame.camera_id == "front"
    assert frame.frame_id == "13"
    assert frame.detections == []
    assert protocol.get_observation(now_ms=1000) is None


def test_frame_id_jump_invalidates_batch_until_clean_new_frame_starts() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    protocol.try_parse_observation(
        "camera_id=front,frame_id=21,category=cargo,left=100,top=20,right=140,bottom=90",
        source="uart6",
        now_ms=1000,
    )
    protocol.try_parse_observation(
        "camera_id=front,frame_id=22,category=follower,left=150,top=25,right=190,bottom=95",
        source="uart6",
        now_ms=1001,
    )
    protocol.try_parse_observation(
        "camera_id=front,frame_id=22,category=cargo,left=200,top=30,right=240,bottom=100",
        source="uart6",
        now_ms=1002,
    )
    protocol.try_parse_observation(
        "camera_id=front,frame_id=22,frame_end=1",
        source="uart6",
        now_ms=1003,
    )

    assert protocol.get_frame(now_ms=1003) is None
    assert protocol.get_observation(now_ms=1003) is None

    protocol.try_parse_observation(
        "camera_id=front,frame_id=23,category=follower,left=160,top=35,right=210,bottom=110",
        source="uart6",
        now_ms=1004,
    )
    protocol.try_parse_observation(
        "camera_id=front,frame_id=23,frame_end=1",
        source="uart6",
        now_ms=1005,
    )

    frame = protocol.get_frame(now_ms=1005)
    assert frame is not None
    assert frame.frame_id == "23"
    assert [item.category for item in frame.detections] == ["follower"]


def test_invalidated_old_frame_end_does_not_commit_empty_frame() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    protocol.try_parse_observation(
        "camera_id=front,frame_id=21,category=cargo,left=100,top=20,right=140,bottom=90",
        source="uart6",
        now_ms=1000,
    )
    protocol.try_parse_observation(
        "camera_id=front,frame_id=22,category=follower,left=150,top=25,right=190,bottom=95",
        source="uart6",
        now_ms=1001,
    )
    protocol.try_parse_observation(
        "camera_id=front,frame_id=21,frame_end=1",
        source="uart6",
        now_ms=1002,
    )

    assert protocol.get_frame(now_ms=1002) is None
    assert protocol.get_observation(now_ms=1002) is None


def test_camera_id_jump_invalidates_batch_until_clean_new_frame_starts() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    protocol.try_parse_observation(
        "camera_id=front,frame_id=31,category=cargo,left=100,top=20,right=140,bottom=90",
        source="uart6",
        now_ms=1000,
    )
    protocol.try_parse_observation(
        "camera_id=rear,frame_id=31,category=follower,left=150,top=25,right=190,bottom=95",
        source="uart6",
        now_ms=1001,
    )
    protocol.try_parse_observation(
        "camera_id=rear,frame_id=31,frame_end=1",
        source="uart6",
        now_ms=1002,
    )
    protocol.try_parse_observation(
        "camera_id=front,frame_id=31,frame_end=1",
        source="uart6",
        now_ms=1003,
    )

    assert protocol.get_frame(now_ms=1003) is None
    assert protocol.get_observation(now_ms=1003) is None

    protocol.try_parse_observation(
        "camera_id=rear,frame_id=32,category=follower,left=160,top=35,right=210,bottom=110",
        source="uart6",
        now_ms=1004,
    )
    protocol.try_parse_observation(
        "camera_id=rear,frame_id=32,frame_end=1",
        source="uart6",
        now_ms=1005,
    )

    frame = protocol.get_frame(now_ms=1005)
    assert frame is not None
    assert frame.camera_id == "rear"
    assert frame.frame_id == "32"
    assert [item.category for item in frame.detections] == ["follower"]


def test_non_addressed_camera_stays_silent_on_shared_visual_uart() -> None:
    assert VisionProtocol.build_frame_query("Front") == "?frame=front"
    assert VisionProtocol.is_query_for_camera("?frame=front", "front") is True
    assert VisionProtocol.is_query_for_camera("?frame=front", "rear") is False
    assert VisionProtocol.is_query_for_camera("?frame=rear", "front") is False


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
