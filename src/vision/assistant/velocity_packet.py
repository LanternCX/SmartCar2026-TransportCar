"""辅车速度包共享解析

@file src/vision/assistant/velocity_packet.py
"""

import math

from config import params as _params


CONSUME_IGNORED = "ignored"
CONSUME_ACCEPTED = "accepted"
CONSUME_INVALID = "invalid"

V_CMD_MAX = getattr(_params, "V_CMD_MAX")


def is_velocity_fragment(fragment: str) -> bool:
    """判断片段是否为速度字段

    @param fragment 待判断的文本片段
    @return 是否为速度字段
    """

    text = fragment.strip()
    if not text or "=" not in text:
        return False
    key = text.split("=", 1)[0].strip().lower()
    return key in ("vx", "vy", "omega", "w")


def canonical_velocity_key(key: str):
    """将速度字段名规范化为标准形式

    @param key 原始字段名
    @return 规范化后的字段名或 None
    """

    key = key.strip().lower()
    if key == "vx":
        return "vx"
    if key == "vy":
        return "vy"
    if key == "omega" or key == "w":
        return "omega"
    return None


def clamp_command_value(value: float) -> float:
    """将命令值限制在有效范围内

    @param value 原始值
    @return 限制后的值
    """

    if value > V_CMD_MAX:
        return float(V_CMD_MAX)
    if value < -V_CMD_MAX:
        return float(-V_CMD_MAX)
    return float(value)


def parse_velocity_fragments(fragments):
    """解析速度字段片段

    @param fragments 字段片段列表
    @return 消费结果状态和解析后的速度字典元组
    """

    parsed = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    seen_keys = set()
    accepted = False
    for fragment in fragments:
        item = fragment.strip()
        if not item:
            continue
        if "=" not in item:
            return CONSUME_IGNORED, None
        key, value_text = item.split("=", 1)
        key = canonical_velocity_key(key)
        if key is None:
            return CONSUME_IGNORED, None
        if key in seen_keys:
            return CONSUME_INVALID, None
        try:
            value = float(value_text.strip())
        except ValueError:
            return CONSUME_INVALID, None
        if not math.isfinite(value):
            return CONSUME_INVALID, None
        parsed[key] = clamp_command_value(value)
        seen_keys.add(key)
        accepted = True
    if not accepted:
        return CONSUME_IGNORED, None
    return CONSUME_ACCEPTED, parsed


def split_velocity_line(line: str):
    """分割速度命令行

    将命令行分割为速度字段和非速度字段两部分

    @param line 原始命令行
    @return 消费结果状态、解析后的速度字典、透传命令行元组
    """

    text = line.strip()
    if not text or text.startswith("?"):
        return CONSUME_IGNORED, None, text

    velocity_fragments = []
    passthrough_fragments = []
    for fragment in text.split(","):
        item = fragment.strip()
        if not item:
            continue
        if is_velocity_fragment(item):
            velocity_fragments.append(item)
        else:
            passthrough_fragments.append(item)

    consume_result = CONSUME_IGNORED
    parsed = None
    if velocity_fragments:
        consume_result, parsed = parse_velocity_fragments(velocity_fragments)

    passthrough_line = None
    if passthrough_fragments:
        passthrough_line = ",".join(passthrough_fragments)
    elif consume_result == CONSUME_IGNORED:
        passthrough_line = text

    return consume_result, parsed, passthrough_line
