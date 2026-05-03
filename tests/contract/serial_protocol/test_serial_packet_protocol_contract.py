"""! @brief 串口短包正式协议契约测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.packet import (  # noqa: E402
    format_ack_packet,
    format_event_packet,
    format_observation_packet,
    format_state_sync_packet,
    format_velocity_packet,
    parse_short_packet,
)

def test_formal_short_packet_types_are_parseable() -> None:
    """! @brief 正式短包类型 v/s/a/o/r 都有协议解析边界"""

    assert parse_short_packet("v,1.0,-2.5,0.5")["type"] == "v"
    assert parse_short_packet("s,12,7,3,1,0")["type"] == "s"
    assert parse_short_packet("a,12")["type"] == "a"
    assert parse_short_packet("o,7,1.0,-0.5,3.0")["type"] == "o"
    assert parse_short_packet("r,13,7,2,-1")["type"] == "r"


def test_formal_runtime_packets_use_short_text_format() -> None:
    """! @brief 运行时格式化函数输出短文本包"""

    assert format_velocity_packet(1.0, -2.5, 0.5) == "v,1.0,-2.5,0.5"
    assert format_state_sync_packet(12, 7, 3, 1, 0) == "s,12,7,3,1,0"
    assert format_ack_packet(12) == "a,12"
    assert format_observation_packet(7, 1.0, -0.5, 3.0) == "o,7,1.0,-0.5,3.0"
    assert format_event_packet(13, 7, 2, -1) == "r,13,7,2,-1"


def test_reliable_sequence_is_separate_from_business_context() -> None:
    """! @brief 可靠包确认序号与业务上下文编号必须分开解析"""

    sync_packet = parse_short_packet("s,12,7,3,1,0")
    event_packet = parse_short_packet("r,13,7,6,200")
    observation_packet = parse_short_packet("o,7,1.0,-0.5,200")

    assert sync_packet == {
        "type": "s",
        "reliable_seq": 12,
        "context_id": 7,
        "state": 3,
        "target": 1,
        "arg": 0,
    }
    assert event_packet == {
        "type": "r",
        "reliable_seq": 13,
        "context_id": 7,
        "event": 6,
        "value": 200,
    }
    assert observation_packet == {
        "type": "o",
        "context_id": 7,
        "x": 1.0,
        "y": -0.5,
        "value": 200.0,
    }
    assert parse_short_packet("a,12") == {"type": "a", "reliable_seq": 12}


def test_uart6_master_vision_velocity_packet_uses_generic_short_velocity_without_omega() -> None:
    """! @brief UART6 主车视觉 v 搜索速度包复用通用速度短包解析"""

    assert parse_short_packet("v,0.08,-0.04") == {
        "type": "v",
        "vx": 0.08,
        "vy": -0.04,
        "omega": 0.0,
        "has_omega": False,
    }


def test_uart6_master_vision_reliable_hooks_and_velocity_stream_do_not_conflict() -> None:
    """! @brief UART6 主车视觉可靠事件链路与 v 数据流解析语义互不冲突"""

    packets = [
        parse_short_packet("s,12,7,1,1,1"),
        parse_short_packet("a,12"),
        parse_short_packet("v,0.08,0"),
        parse_short_packet("r,13,7,6,300"),
    ]

    assert packets == [
        {
            "type": "s",
            "reliable_seq": 12,
            "context_id": 7,
            "state": 1,
            "target": 1,
            "arg": 1,
        },
        {"type": "a", "reliable_seq": 12},
        {
            "type": "v",
            "vx": 0.08,
            "vy": 0.0,
            "omega": 0.0,
            "has_omega": False,
        },
        {
            "type": "r",
            "reliable_seq": 13,
            "context_id": 7,
            "event": 6,
            "value": 300,
        },
    ]


def test_uart8_state_sync_packet_keeps_existing_state_fields() -> None:
    """! @brief UART8 状态同步短包使用状态字段"""

    assert parse_short_packet("s,12,3,1,0") == {
        "type": "s",
        "seq": 12,
        "state": 3,
        "target": 1,
        "arg": 0,
    }
    assert parse_short_packet("r,12,2,-1") is None


def test_non_short_packet_velocity_text_is_outside_short_packet_protocol() -> None:
    """! @brief 非短包速度文本不属于正式短包协议"""

    assert parse_short_packet("vx=1,vy=2,omega=3") is None
    assert parse_short_packet("type=stream,state=12,vx=1.2,vy=0.3") is None


def test_non_short_packet_text_is_outside_short_packet_protocol() -> None:
    """! @brief 非短包文本不属于正式短包协议"""

    for line in ("rear=1", "reset", "?health", "diag=1"):
        assert parse_short_packet(line) is None
