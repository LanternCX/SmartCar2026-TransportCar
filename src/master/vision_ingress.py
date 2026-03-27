"""主车视觉接入组织.

@file src/master/vision_ingress.py
"""

from config.params import FOLLOW_ACTIVE_UART, FOLLOW_RESERVED_UARTS, FOLLOW_TARGET_LABEL


def _split_pairs(line):
    """按逗号拆解单行键值对

    @brief 返回保持原顺序的键值列表
    @param line 原始报文文本
    @return list
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


def _pairs_to_map(pairs):
    """将键值列表转为字典

    @brief 遇到重复键时直接报错
    @param pairs 键值列表
    @return dict
    """

    payload = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError("duplicate_key")
        payload[key] = value
    return payload


def _parse_bbox(payload):
    """解析识别框字段

    @brief 仅在报文提供 bbox 时进行校验
    @param payload 视觉载荷字典
    @return dict
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


def _parse_vision_line(line):
    """解析当前专项方案视觉报文

    @brief 只接受 `vision=1,...` 的持续回传格式
    @param line 原始报文文本
    @return dict
    """

    payload = _pairs_to_map(_split_pairs(line))
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
        observation.update(_parse_bbox(payload))
    return observation


class VisionIngress:
    """主车跟随视觉接入器

    @brief 当前只启用单路视觉验收, 同时保留双路装配边界
    """

    def __init__(self, active_uart=FOLLOW_ACTIVE_UART, reserved_uarts=None):
        self.active_uart = str(active_uart)
        if reserved_uarts is None:
            reserved_uarts = FOLLOW_RESERVED_UARTS
        self.reserved_uarts = tuple(reserved_uarts)
        self.latest_vision_seq = 0

    def _build_idle_observation(self, source_status):
        """构造无目标观测

        @brief 为无效输入和预留链路提供统一回退结果
        @param source_status 输入来源状态
        @return dict
        """

        return {
            "active_uart": self.active_uart,
            "reserved_uarts": self.reserved_uarts,
            "source_status": str(source_status),
            "camera_id": FOLLOW_TARGET_LABEL,
            "target": "idle",
            "vision_seq": 0,
            "valid": 0,
            "err_x": 0.0,
            "err_y": 0.0,
        }

    def prepare_observation(self, observation=None):
        """补齐视觉接入上下文后的观测

        @brief 当前只消费 `UART6` 的单路持续回传, `UART8` 仅保留预留位
        @param observation 当前观测字典
        @return dict
        """

        if observation is None:
            return self._build_idle_observation("missing")
        prepared = dict(observation)
        uart_name = str(prepared.get("uart", self.active_uart))
        if uart_name != self.active_uart:
            status = (
                "reserved" if uart_name in self.reserved_uarts else "unexpected_uart"
            )
            return self._build_idle_observation(status)
        line = prepared.get("line")
        if line is None:
            prepared.setdefault("active_uart", self.active_uart)
            prepared.setdefault("reserved_uarts", self.reserved_uarts)
            prepared.setdefault("source_status", "active")
            prepared.setdefault("target", FOLLOW_TARGET_LABEL)
            prepared.setdefault("valid", 0)
            prepared.setdefault("err_x", 0.0)
            prepared.setdefault("err_y", 0.0)
            return prepared
        try:
            parsed = _parse_vision_line(line)
        except (KeyError, TypeError, ValueError):
            return self._build_idle_observation("invalid")
        if int(parsed["vision_seq"]) <= int(self.latest_vision_seq):
            return self._build_idle_observation("stale")
        self.latest_vision_seq = int(parsed["vision_seq"])
        parsed["active_uart"] = self.active_uart
        parsed["reserved_uarts"] = self.reserved_uarts
        parsed["source_status"] = "active"
        return parsed
