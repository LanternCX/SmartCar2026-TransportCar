"""主车视觉协议解析.

@file src/master/vision/parser.py
"""


def split_pairs(line):
    """把视觉协议文本拆成键值对序列.

    @brief 这一层只处理字段切分和基础合法性, 不解释字段业务语义。
    """

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
    """把键值对序列整理成唯一键映射.

    @brief 解析阶段在这里拦截重复字段, 避免后续逻辑默默覆盖输入。
    """

    payload = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError("duplicate_key")
        payload[key] = value
    return payload


def parse_bbox(payload):
    """从协议映射中提取并校验框坐标.

    @brief 只有框字段齐全时才输出结果, 缺字段则保持为空字典让上层继续按最小观测处理。
    """

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
    """解析一整行视觉协议文本.

    @brief 输出主车视觉链统一使用的 observation 字典, 让串口来源与上层决策解耦。
    """

    payload = pairs_to_map(split_pairs(line))
    if payload.get("vision") != "1":
        raise ValueError("unsupported_vision_payload")
    valid = int(payload["valid"])
    observation = {
        "camera_id": str(payload["camera_id"]),
        "vision_seq": int(payload["seq"]),
        "valid": 1 if valid else 0,
        "target": str(payload["target"]),
        "err_x": 0.0,
        "err_y": 0.0,
    }
    if valid:
        observation["err_x"] = float(payload["err_x"])
        observation["err_y"] = float(payload["err_y"])
        observation.update(parse_bbox(payload))
    return observation
