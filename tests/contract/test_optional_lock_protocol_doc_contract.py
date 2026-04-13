"""可选 lock 协议文档契约测试."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    ROOT / ".agents" / "skills" / "using-rules" / "references" / "openart-protocol.md"
)
CONTROL_DOC_PATH = ROOT / "docs" / "developer" / "control.md"


def extract_control_protocol_section(text: str) -> str:
    """截取控制协议正文, 锁住可选 lock 文档口径."""
    start = text.index("## 3. 模块 A：车模控制协议（遥控协议）")
    end = text.index("## 4. 模块 B：车模与视觉端通信协议")
    return text[start:end]


def assert_no_legacy_lock_statements(text: str) -> None:
    """禁止文档回退到“锁期间直接丢弃新命令”的旧口径."""
    forbidden_phrases = [
        "大多数普通控制命令会被忽略",
        "所有新的运动控制指令都被丢弃",
        "收到新的绝对位置指令",
    ]

    for phrase in forbidden_phrases:
        assert phrase not in text, f"legacy lock statement found: {phrase}"


def test_optional_lock_protocol_doc_matches_current_contract() -> None:
    """控制协议正文应包含可选 lock 的当前约定."""
    text = PROTOCOL_PATH.read_text(encoding="utf-8")
    section = extract_control_protocol_section(text)

    required_tokens = [
        "`lock`",
        "`lock=0`",
        "`lock=1`",
        "`command_mode`",
        "`locked`",
        "`unlocked`",
        "`none`",
    ]

    for token in required_tokens:
        assert token in section, f"missing token in control protocol section: {token}"

    assert "无锁覆盖" in section, (
        "missing unlocked override wording in control protocol"
    )
    assert_no_legacy_lock_statements(section)


def test_optional_lock_related_docs_do_not_restore_legacy_lock_wording() -> None:
    """协议文档和控制说明都不应恢复旧的锁语义表述."""
    control_doc = CONTROL_DOC_PATH.read_text(encoding="utf-8")

    assert "lock=0" in control_doc, "missing lock=0 wording in developer control doc"
    assert "?health.command_mode" in control_doc, (
        "missing command_mode guidance in developer control doc"
    )
    assert_no_legacy_lock_statements(control_doc)
