"""主车视觉协议解析.

@file src/master/vision/parser.py
"""

from config.params import FOLLOW_TARGET_LABEL


def split_pairs(line):
    pairs = []
    for field in str(line).strip().split(","):
        item = field.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError("invalid_field")
        key, value = item.split("=", 1)
        key = key.strip().lower()
        if not key:
            raise ValueError("empty_key")
        pairs.append((key, value.strip()))
    return pairs


def pairs_to_map(pairs):
    payload = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError("duplicate_key")
        payload[key] = value
    return payload


def parse_bbox(payload):
    names = ("bbox_left", "bbox_top", "bbox_right", "bbox_bottom")
    if not all(name in payload for name in names):
        return {}
    bbox = {}
    for name in names:
        bbox[name] = float(payload[name])
    if bbox["bbox_right"] <= bbox["bbox_left"]:
        raise ValueError("invalid_bbox")
    if bbox["bbox_bottom"] <= bbox["bbox_top"]:
        raise ValueError("invalid_bbox")
    return bbox


def parse_vision_line(line):
    payload = pairs_to_map(split_pairs(line))
    if payload.get("vision") != "1":
        raise ValueError("unsupported_vision_payload")
    valid = int(payload["valid"])
    observation = {
        "camera_id": str(payload["camera_id"]),
        "vision_seq": int(payload["seq"]),
        "valid": 1 if valid else 0,
        "target": str(payload.get("target", FOLLOW_TARGET_LABEL)),
        "err_x": 0.0,
        "err_y": 0.0,
    }
    if valid:
        observation["err_x"] = float(payload["err_x"])
        observation["err_y"] = float(payload["err_y"])
        observation.update(parse_bbox(payload))
    return observation
