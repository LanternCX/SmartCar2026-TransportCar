"""视觉速度短包共享解析.

@file src/vision/velocity_packet.py
"""

from config import safety as safety_params
from protocol.packet import parse_short_packet


CONSUME_IGNORED = "ignored"
CONSUME_ACCEPTED = "accepted"
CONSUME_INVALID = "invalid"

V_CMD_MAX = getattr(safety_params, "V_CMD_MAX")


def clamp_command_value(value: float) -> float:
    """将命令值限制在有效范围内.

    @param value 原始值
    @return 限制后的值
    """

    if value > V_CMD_MAX:
        return float(V_CMD_MAX)
    if value < -V_CMD_MAX:
        return float(-V_CMD_MAX)
    return float(value)


def normalize_velocity_packet(packet: dict, allow_omega: bool = True) -> dict:
    """将速度短包标准化为共享速度字典.

    @param packet 已解析的速度短包
    @param allow_omega 是否保留角速度字段
    @return 共享速度字典
    """

    parsed = {
        "vx": clamp_command_value(float(packet.get("vx", 0.0))),
        "vy": clamp_command_value(float(packet.get("vy", 0.0))),
        "omega": 0.0,
        "has_omega": False,
    }
    if allow_omega and bool(packet.get("has_omega")):
        parsed["omega"] = clamp_command_value(float(packet.get("omega", 0.0)))
        parsed["has_omega"] = True
    return parsed


def split_velocity_line(line: str, allow_omega: bool = True):
    """解析速度短包行.

    @param line 原始输入行
    @param allow_omega 是否保留角速度字段
    @return 消费结果状态、解析后的速度字典
    """

    text = line.strip()
    if not text:
        return CONSUME_IGNORED, None

    packet = parse_short_packet(text)
    if packet is not None:
        if packet.get("type") != "v":
            return CONSUME_IGNORED, None
        return CONSUME_ACCEPTED, normalize_velocity_packet(
            packet,
            allow_omega=allow_omega,
        )

    if text.lower().startswith("v,"):
        return CONSUME_INVALID, None

    return CONSUME_IGNORED, None
