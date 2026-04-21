"""辅车速度包共享解析.

@file src/vision/assistant/velocity_packet.py
"""

import math

from config import params as _params


CONSUME_IGNORED = "ignored"
CONSUME_ACCEPTED = "accepted"
CONSUME_INVALID = "invalid"

V_CMD_MAX = getattr(_params, "V_CMD_MAX")


def is_velocity_fragment(fragment: str) -> bool:
    text = fragment.strip()
    if not text or "=" not in text:
        return False
    key = text.split("=", 1)[0].strip().lower()
    return key in ("vx", "vy", "omega", "w")


def canonical_velocity_key(key: str):
    key = key.strip().lower()
    if key == "vx":
        return "vx"
    if key == "vy":
        return "vy"
    if key == "omega" or key == "w":
        return "omega"
    return None


def clamp_command_value(value: float) -> float:
    if value > V_CMD_MAX:
        return float(V_CMD_MAX)
    if value < -V_CMD_MAX:
        return float(-V_CMD_MAX)
    return float(value)


def parse_velocity_fragments(fragments):
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
