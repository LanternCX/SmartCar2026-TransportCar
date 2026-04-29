"""辅车速度协议契约测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.assistant.velocity_packet import split_velocity_line  # noqa: E402


def test_assistant_velocity_protocol_accepts_v_short_packet() -> None:
    """车端正式速度协议面识别 v 短包."""
    consume_result, parsed, passthrough_line = split_velocity_line("v,0,0,0")

    assert consume_result == "accepted"
    assert parsed == {"vx": 0.0, "vy": 0.0, "omega": 0.0, "has_omega": True}
    assert passthrough_line is None


def test_assistant_velocity_protocol_rejects_key_value_velocity_text() -> None:
    """键值速度文本不属于正式速度协议面."""
    consume_result, parsed, passthrough_line = split_velocity_line("vx=0,vy=0")

    assert consume_result == "ignored"
    assert parsed is None
    assert passthrough_line == "vx=0,vy=0"
