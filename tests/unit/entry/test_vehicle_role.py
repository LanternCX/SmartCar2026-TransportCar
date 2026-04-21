"""车号识别模块约束测试.

@file tests/unit/entry/test_vehicle_role.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PROJECT_ROOT / "src" / "vision" / "vehicle_role.py"


def load_vehicle_role_module(monkeypatch, pin_cls):
    """按文件路径加载车号识别模块, 并注入假的 Pin 实现."""

    machine_module = ModuleType("machine")
    setattr(machine_module, "Pin", pin_cls)
    monkeypatch.setitem(sys.modules, "machine", machine_module)

    spec = spec_from_file_location("vehicle_role_module", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakePin:
    """测试用假 Pin, 记录初始化参数并返回预置电平."""

    IN = "in"
    PULL_UP_47K = "pull_up_47k"
    values = {"D8": 1, "D9": 1}
    created = []

    def __init__(self, name, mode, pull=None):
        self.name = name
        self.mode = mode
        self.pull = pull
        type(self).created.append((name, mode, pull))

    def value(self):
        return int(type(self).values[self.name])


@pytest.mark.parametrize(
    ("d8_val", "d9_val", "expected_role"),
    ((0, 1, "master"), (1, 0, "assistant")),
)
def test_decode_vehicle_role_accepts_only_confirmed_pairs(
    monkeypatch, d8_val: int, d9_val: int, expected_role: str
) -> None:
    """只有确认过的两组拨码组合属于有效角色."""

    module = load_vehicle_role_module(monkeypatch, _FakePin)

    assert module.decode_vehicle_role(d8_val, d9_val) == expected_role


@pytest.mark.parametrize(("d8_val", "d9_val"), ((0, 0), (1, 1)))
def test_decode_vehicle_role_rejects_invalid_pairs(
    monkeypatch, d8_val: int, d9_val: int
) -> None:
    """其余组合必须按异常处理, 不能静默兜底."""

    module = load_vehicle_role_module(monkeypatch, _FakePin)

    with pytest.raises(ValueError):
        module.decode_vehicle_role(d8_val, d9_val)

