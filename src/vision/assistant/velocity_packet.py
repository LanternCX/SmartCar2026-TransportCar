"""辅车速度短包共享解析

@file src/vision/assistant/velocity_packet.py
"""

from config import params as _params
from vision.serial_protocol import parse_short_packet


CONSUME_IGNORED = "ignored"
CONSUME_ACCEPTED = "accepted"
CONSUME_INVALID = "invalid"

V_CMD_MAX = getattr(_params, "V_CMD_MAX")


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


def split_velocity_line(line: str):
    """解析速度短包行

    @param line 原始输入行
    @return 消费结果状态、解析后的速度字典、透传命令行元组
    """

    text = line.strip()
    if not text:
        return CONSUME_IGNORED, None, text

    packet = parse_short_packet(text)
    if packet is not None:
        if packet.get("type") != "v":
            return CONSUME_IGNORED, None, text
        parsed = {
            "vx": clamp_command_value(float(packet.get("vx", 0.0))),
            "vy": clamp_command_value(float(packet.get("vy", 0.0))),
            "omega": clamp_command_value(float(packet.get("omega", 0.0))),
            "has_omega": bool(packet.get("has_omega")),
        }
        return CONSUME_ACCEPTED, parsed, None

    if text.lower().startswith("v,"):
        return CONSUME_INVALID, None, None

    return CONSUME_IGNORED, None, text
