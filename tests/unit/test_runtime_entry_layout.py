"""单一 src 运行时布局约束.

@file tests/unit/test_runtime_entry_layout.py
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def test_src_runtime_root_matches_v1_3_layout() -> None:
    """当前运行根必须对齐单一 src 布局."""

    assert (SRC_ROOT / "boot.py").exists()

    for directory_name in (
        "config",
        "control",
        "filters",
        "hardware",
        "script",
        "services",
        "storage",
        "utils",
    ):
        assert (SRC_ROOT / directory_name).is_dir()


def test_src_runtime_root_drops_legacy_split_layout() -> None:
    """当前仓库不应再保留旧三套运行结构."""

    for directory_name in ("legacy", "master", "assistant"):
        assert not (SRC_ROOT / directory_name).exists()
