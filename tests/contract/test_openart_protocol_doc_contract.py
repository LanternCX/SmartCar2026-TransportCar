"""OpenArt 正式协议文档契约测试."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    ROOT / ".agents" / "skills" / "using-rules" / "references" / "openart-protocol.md"
)


def extract_visual_protocol_section(text: str) -> str:
    """截取正式视觉协议正文, 用于检查必须存在的新口径."""
    start = text.index("### 4.3 持续回传格式")
    end = text.index("### 4.6 视觉状态诊断接口")
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


def test_openart_protocol_doc_uses_minimal_text_frames_only() -> None:
    """主车仓库正式视觉协议正文必须切到最小文本口径."""
    text = PROTOCOL_PATH.read_text(encoding="utf-8")
    section = extract_visual_protocol_section(text)

    required_tokens = [
        "v=1,s=<seq>,x=<x>,y=<y>",
        "v=0,s=<seq>",
        "`v`",
        "`s`",
        "`x`",
        "`y`",
        "`x` 表示目标中心相对画面中心的横向像素差值",
        "`y` 表示目标底边相对当前期望抓取位置的纵向像素差值",
        "`v=1` 时必须同时携带 `x` 和 `y`",
        "`v=0` 时不发送 `x` 和 `y`",
        "`x > 0` 表示目标在画面中心右侧, `x < 0` 表示目标在画面中心左侧",
        "`y > 0` 表示目标底边超过期望抓取位置, `y < 0` 表示目标底边尚未到达期望抓取位置",
        "`y=0` 表示目标已到达当前设定抓取距离",
        "`v=0` 但仍携带 `x` 或 `y`",
        "缺少 `s`",
        "`v=1` 但缺少 `x` 或 `y`",
    ]

    for token in required_tokens:
        assert token in section, f"missing token in visual protocol section: {token}"
    assert_no_legacy_formal_payloads(text)
