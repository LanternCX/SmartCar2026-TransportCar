"""运行时包布局回归测试."""

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_runtime_packages_define_init_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src"
    packages = (
        "config",
        "control",
        "filters",
        "hardware",
        "services",
        "storage",
        "utils",
    )

    missing = [name for name in packages if not (root / name / "__init__.py").exists()]

    assert missing == []
