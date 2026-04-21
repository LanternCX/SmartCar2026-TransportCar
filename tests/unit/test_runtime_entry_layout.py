"""单一 src 运行时布局约束.

@file tests/unit/test_runtime_entry_layout.py
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def test_src_runtime_root_matches_main_entry_layout() -> None:
    """当前运行根必须对齐单一 src + `main.py` 入口布局."""

    assert (SRC_ROOT / "main.py").exists()
    assert not (SRC_ROOT / "core.py").exists()
    assert not (SRC_ROOT / "boot.py").exists()
    assert (SRC_ROOT / "core" / "runtime.py").exists()
    assert (SRC_ROOT / "vision").is_dir()
    assert (SRC_ROOT / "script").is_dir()


def test_src_runtime_root_drops_legacy_split_layout() -> None:
    """当前仓库不应再保留旧三套运行结构."""

    for directory_name in ("legacy", "master", "assistant"):
        assert not (SRC_ROOT / directory_name).exists()


def test_vision_runtime_uses_role_packages() -> None:
    """视觉角色入口应组织成 master/assistant 包, 便于后续按职责扩展."""

    vision_root = SRC_ROOT / "vision"

    assert (vision_root / "master").is_dir()
    assert (vision_root / "master" / "__init__.py").exists()
    assert (vision_root / "assistant").is_dir()
    assert (vision_root / "assistant" / "__init__.py").exists()
    assert not (vision_root / "master_runtime.py").exists()
    assert not (vision_root / "assistant_runtime.py").exists()
