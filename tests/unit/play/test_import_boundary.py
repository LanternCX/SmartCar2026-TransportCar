"""Play 导入边界测试."""

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"


def test_play_package_import_does_not_load_runner_or_context(monkeypatch) -> None:
    """Play 包入口不能聚合加载运行器和上下文."""

    monkeypatch.syspath_prepend(str(SRC))
    for module_name in (
        "play",
        "play.base",
        "play.context",
        "play.runner",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("play")

    assert "play.base" not in sys.modules
    assert "play.context" not in sys.modules
    assert "play.runner" not in sys.modules
