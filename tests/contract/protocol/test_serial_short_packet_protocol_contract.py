"""串口短包正式协议契约测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.serial_protocol import (  # noqa: E402
    format_ack_packet,
    format_event_packet,
    format_state_sync_packet,
    format_velocity_packet,
    parse_short_packet,
)


def test_formal_short_packet_types_are_parseable() -> None:
    """正式短包类型 v/s/a/o/r 都有协议解析边界."""

    assert parse_short_packet("v,1.0,-2.5,0.5")["type"] == "v"
    assert parse_short_packet("s,12,3,1,0")["type"] == "s"
    assert parse_short_packet("a,12")["type"] == "a"
    assert parse_short_packet("o,12,1.0,-0.5,3.0")["type"] == "o"
    assert parse_short_packet("r,12,2,-1")["type"] == "r"


def test_formal_runtime_packets_use_short_text_format() -> None:
    """运行时格式化函数输出短文本包."""

    assert format_velocity_packet(1.0, -2.5, 0.5) == "v,1.0,-2.5,0.5"
    assert format_state_sync_packet(12, 3, 1, 0) == "s,12,3,1,0"
    assert format_ack_packet(12) == "a,12"
    assert format_event_packet(12, 2, -1) == "r,12,2,-1"


def test_key_value_velocity_text_is_outside_short_packet_protocol() -> None:
    """键值速度文本不属于正式短包协议."""

    assert parse_short_packet("vx=1,vy=2,omega=3") is None
    assert parse_short_packet("type=stream,state=12,vx=1.2,vy=0.3") is None
