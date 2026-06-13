"""! @brief Topic 注册表测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.frame import MODE_TCP, MODE_UDP  # noqa: E402
from protocol.topic import (  # noqa: E402
    ROLE_ASSISTANT,
    ROLE_MASTER,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_ASSISTANT_VISION_EVENT_REPORT,
    TOPIC_ASSISTANT_VISION_TASK_SYNC,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_EVENT_REPORT,
    TOPIC_MASTER_VISION_TASK_SYNC,
    TOPIC_VISION_OBSERVATION,
    UART6,
    UART8,
    can_role_read,
    can_role_write,
    get_topic_spec,
    validate_body_bytes,
    validate_mode_for_topic,
    validate_port_for_topic,
)


def test_all_formal_topics_are_registered_with_expected_metadata() -> None:
    assert get_topic_spec(TOPIC_LOCAL_VISION_VELOCITY) == {
        "name": "LOCAL_VISION_VELOCITY",
        "mode": MODE_UDP,
        "port": UART6,
        "body_size": 7,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY) == {
        "name": "ASSISTANT_FEEDFORWARD_VELOCITY",
        "mode": MODE_UDP,
        "port": UART8,
        "body_size": 7,
    }
    assert get_topic_spec(TOPIC_VISION_OBSERVATION) == {
        "name": "VISION_OBSERVATION",
        "mode": MODE_UDP,
        "port": UART6,
        "body_size": 7,
    }
    assert get_topic_spec(TOPIC_MASTER_VISION_TASK_SYNC) == {
        "name": "MASTER_VISION_TASK_SYNC",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 5,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_VISION_TASK_SYNC) == {
        "name": "ASSISTANT_VISION_TASK_SYNC",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 4,
    }
    assert get_topic_spec(TOPIC_MASTER_VISION_EVENT_REPORT) == {
        "name": "MASTER_VISION_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 4,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_VISION_EVENT_REPORT) == {
        "name": "ASSISTANT_VISION_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 3,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_STATE_SYNC) == {
        "name": "ASSISTANT_STATE_SYNC",
        "mode": MODE_TCP,
        "port": UART8,
        "body_size": 4,
    }
    assert get_topic_spec(TOPIC_ASSISTANT_EVENT_REPORT) == {
        "name": "ASSISTANT_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART8,
        "body_size": 3,
    }


def test_topic_registry_rejects_unregistered_mode_port_and_role_direction() -> None:
    assert get_topic_spec(0x99) is None
    assert validate_mode_for_topic(TOPIC_LOCAL_VISION_VELOCITY, MODE_TCP) is False
    assert validate_port_for_topic(TOPIC_LOCAL_VISION_VELOCITY, UART8) is False
    assert can_role_write(TOPIC_LOCAL_VISION_VELOCITY, ROLE_MASTER) is False
    assert can_role_read(TOPIC_LOCAL_VISION_VELOCITY, ROLE_MASTER) is True
    assert can_role_write(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY, ROLE_MASTER) is True
    assert can_role_read(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY, ROLE_MASTER) is False
    assert can_role_write(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY, ROLE_ASSISTANT) is False
    assert can_role_read(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY, ROLE_ASSISTANT) is True


def test_topic_registry_rejects_wrong_body_type_and_length() -> None:
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, b"\x00" * 7) is True
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, bytearray(7)) is True
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, memoryview(b"\x00" * 7)) is True
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, "abc") is False
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, b"\x00" * 6) is False
    assert validate_body_bytes(TOPIC_LOCAL_VISION_VELOCITY, b"\x00" * 8) is False
