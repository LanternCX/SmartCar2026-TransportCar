"""
@file src/protocol/topic.py
@brief Topic 注册表与方向约束
"""

from protocol.frame import MODE_TCP, MODE_UDP

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


ROLE_MASTER = "master"
ROLE_ASSISTANT = "assistant"

UART6 = "uart6"
UART8 = "uart8"

TOPIC_LOCAL_VISION_VELOCITY = const(0x01)
TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY = const(0x02)
TOPIC_VISION_OBSERVATION = const(0x03)
TOPIC_LOCAL_VISION_CONTROL = const(0x04)
TOPIC_MASTER_VISION_TASK_SYNC = const(0x10)
TOPIC_ASSISTANT_VISION_TASK_SYNC = const(0x11)
TOPIC_MASTER_VISION_EVENT_REPORT = const(0x12)
TOPIC_ASSISTANT_VISION_EVENT_REPORT = const(0x13)
TOPIC_ASSISTANT_STATE_SYNC = const(0x20)
TOPIC_ASSISTANT_EVENT_REPORT = const(0x21)

_ENTRY_TOPIC = const(0)
_ENTRY_MODE = const(1)
_ENTRY_PORT = const(2)
_ENTRY_BODY_SIZE = const(3)
_ENTRY_READ_MASK = const(4)
_ENTRY_WRITE_MASK = const(5)

_PORT_UART6 = const(6)
_PORT_UART8 = const(8)
_ROLE_MASTER_MASK = const(1)
_ROLE_ASSISTANT_MASK = const(2)
_ROLE_BOTH_MASK = const(3)

_TOPIC_TABLE = (
    (TOPIC_LOCAL_VISION_VELOCITY, MODE_UDP, _PORT_UART6, 7, _ROLE_BOTH_MASK, 0),
    (
        TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
        MODE_UDP,
        _PORT_UART8,
        7,
        _ROLE_ASSISTANT_MASK,
        _ROLE_MASTER_MASK,
    ),
    (TOPIC_VISION_OBSERVATION, MODE_UDP, _PORT_UART6, 7, _ROLE_BOTH_MASK, 0),
    (
        TOPIC_LOCAL_VISION_CONTROL,
        MODE_TCP,
        _PORT_UART6,
        1,
        _ROLE_BOTH_MASK,
        _ROLE_BOTH_MASK,
    ),
    (TOPIC_MASTER_VISION_TASK_SYNC, MODE_TCP, _PORT_UART6, 5, 0, _ROLE_MASTER_MASK),
    (
        TOPIC_ASSISTANT_VISION_TASK_SYNC,
        MODE_TCP,
        _PORT_UART6,
        10,
        0,
        _ROLE_ASSISTANT_MASK,
    ),
    (TOPIC_MASTER_VISION_EVENT_REPORT, MODE_TCP, _PORT_UART6, 10, _ROLE_MASTER_MASK, 0),
    (
        TOPIC_ASSISTANT_VISION_EVENT_REPORT,
        MODE_TCP,
        _PORT_UART6,
        3,
        _ROLE_ASSISTANT_MASK,
        0,
    ),
    (TOPIC_ASSISTANT_STATE_SYNC, MODE_TCP, _PORT_UART8, 10, _ROLE_ASSISTANT_MASK, _ROLE_MASTER_MASK),
    (TOPIC_ASSISTANT_EVENT_REPORT, MODE_TCP, _PORT_UART8, 3, _ROLE_MASTER_MASK, _ROLE_ASSISTANT_MASK),
)


def _find_topic_entry(topic):
    topic = int(topic)
    for entry in _TOPIC_TABLE:
        if int(entry[_ENTRY_TOPIC]) == topic:
            return entry
    return None


def _role_mask(role):
    if role == ROLE_MASTER:
        return _ROLE_MASTER_MASK
    if role == ROLE_ASSISTANT:
        return _ROLE_ASSISTANT_MASK
    return 0


def _port_code(port):
    if port == UART6:
        return _PORT_UART6
    if port == UART8:
        return _PORT_UART8
    return 0


def _port_name(port_code):
    if int(port_code) == _PORT_UART6:
        return UART6
    if int(port_code) == _PORT_UART8:
        return UART8
    return None


def _topic_name(topic):
    topic = int(topic)
    if topic == TOPIC_LOCAL_VISION_VELOCITY:
        return "LOCAL_VISION_VELOCITY"
    if topic == TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY:
        return "ASSISTANT_FEEDFORWARD_VELOCITY"
    if topic == TOPIC_VISION_OBSERVATION:
        return "VISION_OBSERVATION"
    if topic == TOPIC_LOCAL_VISION_CONTROL:
        return "LOCAL_VISION_CONTROL"
    if topic == TOPIC_MASTER_VISION_TASK_SYNC:
        return "MASTER_VISION_TASK_SYNC"
    if topic == TOPIC_ASSISTANT_VISION_TASK_SYNC:
        return "ASSISTANT_VISION_TASK_SYNC"
    if topic == TOPIC_MASTER_VISION_EVENT_REPORT:
        return "MASTER_VISION_EVENT_REPORT"
    if topic == TOPIC_ASSISTANT_VISION_EVENT_REPORT:
        return "ASSISTANT_VISION_EVENT_REPORT"
    if topic == TOPIC_ASSISTANT_STATE_SYNC:
        return "ASSISTANT_STATE_SYNC"
    if topic == TOPIC_ASSISTANT_EVENT_REPORT:
        return "ASSISTANT_EVENT_REPORT"
    return None


def get_topic_spec(topic):
    """返回测试友好的最小 topic 信息."""

    entry = _find_topic_entry(topic)
    if entry is None:
        return None
    return {
        "name": _topic_name(topic),
        "mode": entry[_ENTRY_MODE],
        "port": _port_name(entry[_ENTRY_PORT]),
        "body_size": entry[_ENTRY_BODY_SIZE],
    }


def get_topic_entry(topic):
    """返回 topic 注册表完整信息."""

    return _find_topic_entry(topic)


def get_topic_body_size(topic):
    entry = _find_topic_entry(topic)
    if entry is None:
        return -1
    return int(entry[_ENTRY_BODY_SIZE])


def validate_mode_for_topic(topic, mode):
    entry = _find_topic_entry(topic)
    if entry is None:
        return False
    return int(mode) == int(entry[_ENTRY_MODE])


def validate_port_for_topic(topic, port):
    entry = _find_topic_entry(topic)
    if entry is None:
        return False
    return _port_code(port) == int(entry[_ENTRY_PORT])


def can_role_read(topic, role):
    entry = _find_topic_entry(topic)
    if entry is None:
        return False
    return bool(_role_mask(role) & int(entry[_ENTRY_READ_MASK]))


def can_role_write(topic, role):
    entry = _find_topic_entry(topic)
    if entry is None:
        return False
    return bool(_role_mask(role) & int(entry[_ENTRY_WRITE_MASK]))


def validate_body_bytes(topic, body):
    body_size = get_topic_body_size(topic)
    if body_size < 0:
        return False
    if isinstance(body, str):
        return False
    if isinstance(body, bytes):
        size = len(body)
    elif isinstance(body, bytearray):
        size = len(body)
    elif isinstance(body, memoryview):
        size = len(body)
    else:
        return False
    return size == body_size
