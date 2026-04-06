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


def parse_vision_line(line):
    """解析一整行视觉协议文本.

    @brief 输出主车视觉链统一使用的 observation 字典, 让串口来源与上层决策解耦。
    """

    payload = pairs_to_map(split_pairs(line))
    allowed_keys = ("v", "s", "x", "y")
    for key in payload:
        if key not in allowed_keys:
            raise ValueError("unexpected_key")
    if "s" not in payload:
        raise ValueError("missing_seq")
    if "v" not in payload:
        raise ValueError("missing_valid_flag")
    valid = int(payload["v"])
    if valid not in (0, 1):
        raise ValueError("invalid_valid_flag")
    observation = {
        "vision_seq": int(payload["s"]),
        "valid": valid,
        "err_x": 0.0,
        "err_y": 0.0,
    }
    if valid == 1:
        if "x" not in payload or "y" not in payload:
            raise ValueError("missing_xy")
        observation["err_x"] = float(payload["x"])
        observation["err_y"] = float(payload["y"])
    elif "x" in payload or "y" in payload:
        raise ValueError("unexpected_xy_for_invalid_frame")
    return observation
