"""新运行时入口布局约束.

@file tests/unit/test_runtime_entry_layout.py
"""

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_master_and_assistant_only_keep_main_entry() -> None:
    """新运行时只保留 main.py 作为公开入口."""

    for runtime_name in ("master", "assistant"):
        runtime_root = PROJECT_ROOT / "src" / runtime_name
        assert (runtime_root / "main.py").exists()
        assert not (runtime_root / "boot.py").exists()


def test_master_and_assistant_expose_new_structure_directories() -> None:
    """主辅车当前阶段必须先落新框架目录边界."""

    expected = {
        "master": ("hw", "ctrl", "vision", "script"),
        "assistant": ("hw", "ctrl", "script"),
    }

    for runtime_name, directory_names in expected.items():
        runtime_root = PROJECT_ROOT / "src" / runtime_name
        for directory_name in directory_names:
            assert (runtime_root / directory_name).is_dir()


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
