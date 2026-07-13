"""! @brief 业务 body bytes 编解码测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.codec import (  # noqa: E402
    AE_EVENT,
    AE_VALUE,
    AS_ARG,
    AS_STATE,
    AS_TARGET,
    CTL_ACTION,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    ME_CTX,
    ME_EVENT,
    ME_VALUE,
    MT_ARG,
    MT_CTX,
    MT_STATE,
    MT_TARGET,
    VEL_HAS_W,
    VEL_W,
    VEL_X,
    VEL_Y,
    VO_CTX,
    VO_VALUE,
    VO_X,
    VO_Y,
    decode_assistant_event_report_body,
    decode_assistant_state_sync_body,
    decode_assistant_vision_event_report_body,
    decode_assistant_vision_task_sync_body,
    decode_local_vision_control_body,
    decode_master_vision_event_report_body,
    decode_master_vision_task_sync_body,
    decode_velocity_body_into,
    decode_velocity_body,
    decode_vision_observation_body,
    encode_assistant_event_report_body,
    encode_assistant_state_sync_body,
    encode_assistant_vision_event_report_body,
    encode_assistant_vision_task_sync_body,
    encode_local_vision_control_body,
    encode_master_vision_event_report_body,
    encode_master_vision_task_sync_body,
    encode_velocity_body,
    encode_vision_observation_body,
)


def test_velocity_body_roundtrip_uses_little_endian_fixed_point() -> None:
    body = encode_velocity_body(1.25, -0.5, 0.75, True)

    assert body == bytes([0xE2, 0x04, 0x0C, 0xFE, 0xEE, 0x02, 0x01])
    assert decode_velocity_body(body) == (1.25, -0.5, 0.75, True)


def test_velocity_body_can_decode_into_reused_slot() -> None:
    body = encode_velocity_body(1.25, -0.5, 0.75, True)
    out = [0.0, 0.0, 0.0, False]

    result = decode_velocity_body_into(body, out)

    assert result is out
    assert out[VEL_X] == 1.25
    assert out[VEL_Y] == -0.5
    assert out[VEL_W] == 0.75
    assert out[VEL_HAS_W] is True


def test_velocity_body_roundtrip_without_omega_flag() -> None:
    body = encode_velocity_body(0.08, -0.04, 0.0, False)

    assert decode_velocity_body(body) == (0.08, -0.04, 0.0, False)


def test_velocity_body_saturates_to_i16_range() -> None:
    body = encode_velocity_body(99.0, -99.0, 0.0, False)

    assert body[:6] == bytes([0xFF, 0x7F, 0x00, 0x80, 0x00, 0x00])


def test_vision_observation_body_roundtrip() -> None:
    body = encode_vision_observation_body(7, 1.0, -0.5, 3.0)

    assert body == bytes([7, 0xE8, 0x03, 0x0C, 0xFE, 0xB8, 0x0B])
    packet = decode_vision_observation_body(body)
    assert packet[VO_CTX] == 7
    assert packet[VO_X] == 1.0
    assert packet[VO_Y] == -0.5
    assert packet[VO_VALUE] == 3.0


def test_local_vision_control_body_roundtrip() -> None:
    gate_on_body = encode_local_vision_control_body(LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON)
    gate_off_body = encode_local_vision_control_body(LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF)

    assert gate_on_body == bytes([1])
    assert gate_off_body == bytes([2])
    assert (
        decode_local_vision_control_body(gate_on_body)[CTL_ACTION]
        == LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON
    )
    assert (
        decode_local_vision_control_body(gate_off_body)[CTL_ACTION]
        == LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF
    )


def test_master_task_sync_body_roundtrip() -> None:
    body = encode_master_vision_task_sync_body(9, 1, 3, -2)

    assert body == bytes([9, 1, 3, 0xFE, 0xFF])
    packet = decode_master_vision_task_sync_body(body)
    assert packet[MT_CTX] == 9
    assert packet[MT_STATE] == 1
    assert packet[MT_TARGET] == 3
    assert packet[MT_ARG] == -2


def test_assistant_vision_task_sync_body_roundtrip() -> None:
    body = encode_assistant_vision_task_sync_body(2, 1, 17)

    assert body == bytes([2, 1, 17, 0])
    packet = decode_assistant_vision_task_sync_body(body)
    assert packet[AS_STATE] == 2
    assert packet[AS_TARGET] == 1
    assert packet[AS_ARG] == 17
    assert len(packet) == 3


def test_master_vision_event_report_body_roundtrip() -> None:
    body = encode_master_vision_event_report_body(5, 6, 200)

    assert body == bytes([5, 6, 200, 0])
    packet = decode_master_vision_event_report_body(body)
    assert packet[ME_CTX] == 5
    assert packet[ME_EVENT] == 6
    assert packet[ME_VALUE] == 200
    assert len(packet) == 3


def test_assistant_vision_event_report_body_roundtrip() -> None:
    body = encode_assistant_vision_event_report_body(7, -1)

    assert body == bytes([7, 0xFF, 0xFF])
    packet = decode_assistant_vision_event_report_body(body)
    assert packet[AE_EVENT] == 7
    assert packet[AE_VALUE] == -1


def test_assistant_state_sync_body_roundtrip() -> None:
    body = encode_assistant_state_sync_body(4, 1, 23)

    assert body == bytes([4, 1, 23, 0])
    packet = decode_assistant_state_sync_body(body)
    assert packet[AS_STATE] == 4
    assert packet[AS_TARGET] == 1
    assert packet[AS_ARG] == 23
    assert len(packet) == 3


def test_assistant_event_report_body_roundtrip() -> None:
    body = encode_assistant_event_report_body(9, -3)

    assert body == bytes([9, 0xFD, 0xFF])
    packet = decode_assistant_event_report_body(body)
    assert packet[AE_EVENT] == 9
    assert packet[AE_VALUE] == -3


def test_codec_avoids_board_unstable_int_byte_helpers() -> None:
    source = (SRC / "protocol" / "codec.py").read_text(encoding="utf-8")

    assert ".to_bytes(" not in source
    assert "int.from_bytes(" not in source
