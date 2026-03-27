"""主车视觉输入整理

@file src/master/vision_ingress.py
"""

from config.params import FOLLOW_ACTIVE_UART, FOLLOW_RESERVED_UARTS, FOLLOW_TARGET_LABEL


def _split_pairs(line):
    """按逗号拆解单行键值对

    @brief 将视觉报文拆解为有序键值对列表
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

    @brief 保留键值映射并拒绝重复键
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

    @brief 报文带有完整 bbox 字段时执行边界校验
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
    """解析视觉链路回传的单行报文

    @brief 将协议文本转换为主车内部观测字典
    @param line 原始报文文本
    @return dict
    """

    payload = _pairs_to_map(_split_pairs(line))
    if payload.get("vision") != "1":
        raise ValueError("unsupported_vision_payload")
    valid = int(payload["valid"])

    # 无目标时仍返回完整观测结构, 只将误差项保持为零
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
    """负责整理主车视觉链路输入

    @brief 校验输入链路、解析报文并补齐观测上下文
    """

    def __init__(self, active_uart=FOLLOW_ACTIVE_UART, reserved_uarts=None):
        # 启用链路和预留链路配置保存在接入层, 便于统一判定输入来源
        self.active_uart = str(active_uart)
        if reserved_uarts is None:
            reserved_uarts = FOLLOW_RESERVED_UARTS
        self.reserved_uarts = tuple(reserved_uarts)

        # 最近一次视觉序号用于过滤重复或回退报文
        self.latest_vision_seq = 0

    def _build_idle_observation(self, source_status):
        """构造空闲观测结果

        @brief 为无效输入和非启用链路返回统一观测结构
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
        """整理并补齐主车观测

        @brief 过滤链路异常和过期报文, 返回统一观测结构
        @param observation 当前观测字典
        @return dict
        """

        if observation is None:
            return self._build_idle_observation("missing")
        prepared = dict(observation)
        uart_name = str(prepared.get("uart", self.active_uart))

        # 非启用链路统一回退为空闲观测, 由上层决定是否忽略
        if uart_name != self.active_uart:
            status = (
                "reserved" if uart_name in self.reserved_uarts else "unexpected_uart"
            )
            return self._build_idle_observation(status)

        line = prepared.get("line")
        if line is None:
            # 已经是结构化观测时只补齐缺省上下文, 不重复解析协议文本
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

        # 视觉序号必须前进, 避免旧报文覆盖新状态
        if int(parsed["vision_seq"]) <= int(self.latest_vision_seq):
            return self._build_idle_observation("stale")
        self.latest_vision_seq = int(parsed["vision_seq"])
        parsed["active_uart"] = self.active_uart
        parsed["reserved_uarts"] = self.reserved_uarts
        parsed["source_status"] = "active"
        return parsed
