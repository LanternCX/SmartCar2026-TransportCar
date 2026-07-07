"""导入边界测试."""

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"


def test_protocol_package_import_does_not_load_transport(monkeypatch) -> None:
    """协议包入口不能聚合加载通信实现."""

    monkeypatch.syspath_prepend(str(SRC))
    for module_name in (
        "protocol",
        "protocol.frame",
        "protocol.topic",
        "protocol.transport",
    ):
        sys.modules.pop(module_name, None)

    importlib.import_module("protocol")

    assert "protocol.frame" not in sys.modules
    assert "protocol.topic" not in sys.modules
    assert "protocol.transport" not in sys.modules
