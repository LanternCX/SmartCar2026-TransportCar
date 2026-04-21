"""辅车速度协议契约测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.assistant.velocity_packet import split_velocity_line


def test_assistant_velocity_protocol_accepts_minimal_vx_vy_zero_frame() -> None:
    """车端当前协议面应继续识别 vx/vy 零值帧."""
    consume_result, parsed, passthrough_line = split_velocity_line("vx=0,vy=0")

    assert consume_result == "accepted"
    assert parsed == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert passthrough_line is None


def test_assistant_velocity_protocol_keeps_follow_metadata_outside_current_mainline() -> None:
    """旧的 follow 元信息不属于当前正式速度协议面."""
    consume_result, parsed, passthrough_line = split_velocity_line(
        "follow=1,seq=3,valid=0,dx=0,dy=0"
    )

    assert consume_result == "ignored"
    assert parsed is None
    assert passthrough_line == "follow=1,seq=3,valid=0,dx=0,dy=0"
