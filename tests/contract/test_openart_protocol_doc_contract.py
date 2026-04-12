"""OpenArt 正式协议文档契约测试."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    ROOT / ".agents" / "skills" / "using-rules" / "references" / "openart-protocol.md"
)


def extract_visual_protocol_section(text: str) -> str:
    """截取正式视觉协议正文, 用于检查必须存在的新口径."""
    start = text.index("## 4. 模块 B：车模与视觉端通信协议")
    end = text.index("## 5.") if "## 5." in text else len(text)
    return text[start:end]


def assert_no_legacy_formal_payloads(text: str) -> None:
    """全文禁止回填旧正式长报文字段或旧框格式示例."""
    forbidden_patterns = [
        r"vision\s*=\s*1",
        r"camera_id",
        r"target\s*=",
        r"err_x\s*=",
        r"err_y\s*=",
        r"bbox_left\s*=",
        r"bbox_top\s*=",
        r"bbox_right\s*=",
        r"bbox_bottom\s*=",
        r"\bleft\s*=\s*<",
        r"\btop\s*=\s*<",
        r"\bright\s*=\s*<",
        r"\bbottom\s*=\s*<",
        r"left/top/right/bottom",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, text) is None, (
            f"legacy formal payload found: {pattern}"
        )


def test_openart_protocol_doc_matches_current_visual_facts() -> None:
    """正式视觉协议正文应与当前代码事实一致."""
    text = PROTOCOL_PATH.read_text(encoding="utf-8")
    section = extract_visual_protocol_section(text)

    required_tokens = [
        "`UART6`",
        "x=<x>,y=<y>",
        "`x`",
        "`y`",
        "观测值",
        "OpenArt -> RT1021",
        "不是动作命令",
        "来源不是 `UART6`",
        "缺少 `x` 或 `y`",
        "除 `x`、`y` 之外出现其他键",
    ]

    for token in required_tokens:
        assert token in section, f"missing token in visual protocol section: {token}"
    assert_no_legacy_formal_payloads(text)
