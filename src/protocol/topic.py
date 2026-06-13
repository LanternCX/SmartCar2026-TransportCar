"""
@file src/protocol/topic.py
@brief Topic 注册表与方向约束
"""

from protocol.frame import MODE_TCP, MODE_UDP


ROLE_MASTER = "master"
ROLE_ASSISTANT = "assistant"

UART6 = "uart6"
UART8 = "uart8"

TOPIC_LOCAL_VISION_VELOCITY = 0x01
TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY = 0x02
TOPIC_VISION_OBSERVATION = 0x03
TOPIC_MASTER_VISION_TASK_SYNC = 0x10
TOPIC_ASSISTANT_VISION_TASK_SYNC = 0x11
TOPIC_MASTER_VISION_EVENT_REPORT = 0x12
TOPIC_ASSISTANT_VISION_EVENT_REPORT = 0x13
TOPIC_ASSISTANT_STATE_SYNC = 0x20
TOPIC_ASSISTANT_EVENT_REPORT = 0x21

_TOPIC_TABLE = {
    TOPIC_LOCAL_VISION_VELOCITY: {
        "name": "LOCAL_VISION_VELOCITY",
        "mode": MODE_UDP,
        "port": UART6,
        "body_size": 7,
        "read_roles": (ROLE_MASTER, ROLE_ASSISTANT),
        "write_roles": (),
    },
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY: {
        "name": "ASSISTANT_FEEDFORWARD_VELOCITY",
        "mode": MODE_UDP,
        "port": UART8,
        "body_size": 7,
        "read_roles": (ROLE_ASSISTANT,),
        "write_roles": (ROLE_MASTER,),
    },
    TOPIC_VISION_OBSERVATION: {
        "name": "VISION_OBSERVATION",
        "mode": MODE_UDP,
        "port": UART6,
        "body_size": 7,
        "read_roles": (ROLE_MASTER, ROLE_ASSISTANT),
        "write_roles": (),
    },
    TOPIC_MASTER_VISION_TASK_SYNC: {
        "name": "MASTER_VISION_TASK_SYNC",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 5,
        "read_roles": (),
        "write_roles": (ROLE_MASTER,),
    },
    TOPIC_ASSISTANT_VISION_TASK_SYNC: {
        "name": "ASSISTANT_VISION_TASK_SYNC",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 4,
        "read_roles": (),
        "write_roles": (ROLE_ASSISTANT,),
    },
    TOPIC_MASTER_VISION_EVENT_REPORT: {
        "name": "MASTER_VISION_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 4,
        "read_roles": (ROLE_MASTER,),
        "write_roles": (),
    },
    TOPIC_ASSISTANT_VISION_EVENT_REPORT: {
        "name": "ASSISTANT_VISION_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART6,
        "body_size": 3,
        "read_roles": (ROLE_ASSISTANT,),
        "write_roles": (),
    },
    TOPIC_ASSISTANT_STATE_SYNC: {
        "name": "ASSISTANT_STATE_SYNC",
        "mode": MODE_TCP,
        "port": UART8,
        "body_size": 4,
        "read_roles": (ROLE_ASSISTANT,),
        "write_roles": (ROLE_MASTER,),
    },
    TOPIC_ASSISTANT_EVENT_REPORT: {
        "name": "ASSISTANT_EVENT_REPORT",
        "mode": MODE_TCP,
        "port": UART8,
        "body_size": 3,
        "read_roles": (ROLE_MASTER,),
        "write_roles": (ROLE_ASSISTANT,),
    },
}


def get_topic_spec(topic):
    """返回测试友好的最小 topic 信息."""

    entry = _TOPIC_TABLE.get(int(topic))
    if entry is None:
        return None
    return {
        "name": entry["name"],
        "mode": entry["mode"],
        "port": entry["port"],
        "body_size": entry["body_size"],
    }


def get_topic_entry(topic):
    """返回 topic 注册表完整信息."""

    return _TOPIC_TABLE.get(int(topic))


def validate_mode_for_topic(topic, mode):
    entry = get_topic_entry(topic)
    if entry is None:
        return False
    return int(mode) == int(entry["mode"])


def validate_port_for_topic(topic, port):
    entry = get_topic_entry(topic)
    if entry is None:
        return False
    return port == entry["port"]


def can_role_read(topic, role):
    entry = get_topic_entry(topic)
    if entry is None:
        return False
    return role in entry["read_roles"]


def can_role_write(topic, role):
    entry = get_topic_entry(topic)
    if entry is None:
        return False
    return role in entry["write_roles"]


def validate_body_bytes(topic, body):
    entry = get_topic_entry(topic)
    if entry is None:
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
    return size == int(entry["body_size"])
