"""OpenArt 正式协议文档契约测试."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    ROOT / ".agents" / "skills" / "using-rules" / "references" / "openart-protocol.md"
)


def extract_visual_protocol_section(text: str) -> str:
    """截取正式视觉协议正文, 用于检查当前视觉骨架口径."""
    start = text.index("## 4. 模块 B：车模与视觉端通信协议")
    end = text.index("## 5.") if "## 5." in text else len(text)
    return text[start:end]


def assert_no_legacy_visual_runtime_facts(text: str) -> None:
    """视觉协议正文中禁止回填已删除的旧运行时事实."""
    forbidden_patterns = [
        r"x=<x>,y=<y>",
        r"UART6",
        r"ALIGN_DX",
        r"target_x",
        r"target_y",
        r"target_angle",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, text) is None, (
            f"legacy visual runtime fact found: {pattern}"
        )


def test_openart_protocol_doc_matches_current_visual_facts() -> None:
    """正式视觉协议正文应与当前视觉骨架事实一致."""
    text = PROTOCOL_PATH.read_text(encoding="utf-8")
    section = extract_visual_protocol_section(text)

    required_tokens = [
        "`vision/master/`",
        "`vision/assistant/`",
        "未启用 OpenArt -> RT1021 正式视觉协议",
        "不消费专用视觉串口输入",
        "不提供 `?vision` 查询",
        "共享底盘实例",
    ]

    for token in required_tokens:
        assert token in section, f"missing token in visual protocol section: {token}"
    assert_no_legacy_visual_runtime_facts(section)
