"""新运行时入口布局约束.

@file tests/unit/test_runtime_entry_layout.py
"""

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_master_and_assistant_keep_legacy_entry_shape() -> None:
    """新运行时应保留与旧系统一致的入口层级."""

    for runtime_name in ("master", "assistant"):
        runtime_root = PROJECT_ROOT / "src" / runtime_name
        assert (runtime_root / "boot.py").exists()
        assert (runtime_root / "main.py").exists()


def test_master_and_assistant_runtime_files_do_not_use_typing_module() -> None:
    """运行时代码不应依赖 typing 模块."""

    for runtime_name in ("master", "assistant"):
        runtime_root = PROJECT_ROOT / "src" / runtime_name
        for file_path in runtime_root.rglob("*.py"):
            content = file_path.read_text(encoding="utf-8")
            assert "from typing import" not in content
            assert "import typing" not in content
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("def "):
                    assert "->" not in stripped
                    assert re.search(r"def\s+\w+\([^)]*:[^)]*\)", stripped) is None
