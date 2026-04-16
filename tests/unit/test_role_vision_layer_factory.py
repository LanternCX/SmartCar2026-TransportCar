"""角色视觉运行入口装配约束测试.

@file tests/unit/test_role_vision_layer_factory.py
"""

from importlib import import_module
from pathlib import Path
from types import ModuleType
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def import_vision_package(monkeypatch):
    """按正常包路径导入角色视觉运行入口装配入口."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for module_name in (
        "vision",
        "vision.master",
        "vision.master.runtime",
        "vision.assistant",
        "vision.assistant.runtime",
    ):
        sys.modules.pop(module_name, None)
    return import_module("vision")


def import_runtime_module(module_name, monkeypatch):
    """按正常包路径导入指定视觉运行模块."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    sys.modules.pop(module_name, None)
    return import_module(module_name)


def test_create_role_transport_car_selects_master_branch_only(monkeypatch) -> None:
    """主车装配只能触发主车视觉运行分支."""

    vision_runtime = import_vision_package(monkeypatch)
    calls = []

    master_module = ModuleType("vision.master")
    setattr(
        master_module,
        "create_transport_car",
        lambda: calls.append("master") or {"role": "master"},
    )

    assistant_module = ModuleType("vision.assistant")

    def fail_assistant_create_transport_car():
        raise AssertionError("assistant branch should not be loaded")

    setattr(
        assistant_module,
        "create_transport_car",
        fail_assistant_create_transport_car,
    )

    monkeypatch.setitem(sys.modules, "vision.master", master_module)
    monkeypatch.setitem(sys.modules, "vision.assistant", assistant_module)

    layer = vision_runtime.create_role_transport_car("master")

    assert layer == {"role": "master"}
    assert calls == ["master"]


def test_create_role_transport_car_selects_assistant_branch_only(monkeypatch) -> None:
    """辅车装配只能触发辅车视觉运行分支."""

    vision_runtime = import_vision_package(monkeypatch)
    calls = []

    master_module = ModuleType("vision.master")

    def fail_master_create_transport_car():
        raise AssertionError("master branch should not be loaded")

    setattr(
        master_module,
        "create_transport_car",
        fail_master_create_transport_car,
    )

    assistant_module = ModuleType("vision.assistant")
    setattr(
        assistant_module,
        "create_transport_car",
        lambda: calls.append("assistant") or {"role": "assistant"},
    )

    monkeypatch.setitem(sys.modules, "vision.master", master_module)
    monkeypatch.setitem(sys.modules, "vision.assistant", assistant_module)

    layer = vision_runtime.create_role_transport_car("assistant")

    assert layer == {"role": "assistant"}
    assert calls == ["assistant"]


def test_create_role_transport_car_rejects_unknown_role(monkeypatch) -> None:
    """未知角色必须被拒绝, 不能偷偷回默认分支."""

    vision_runtime = import_vision_package(monkeypatch)

    with pytest.raises(ValueError):
        vision_runtime.create_role_transport_car("unknown")


def test_master_runtime_builds_shared_transport_car(monkeypatch) -> None:
    """主车运行入口当前应回到共享底盘实现."""

    runtime_module = import_runtime_module("vision.master.runtime", monkeypatch)
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")

    class _TransportCar:
        def __init__(self) -> None:
            self.wheel_states = []
            self.imu = "imu"

        def mark_tick(self, _tick=None) -> None:
            return None

        def set_ticker(self, _ticker) -> None:
            return None

        def step(self) -> bool:
            return False

    monkeypatch.setitem(sys.modules, "core", core_package)
    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core.runtime", core_module)

    car = runtime_module.create_transport_car()

    assert isinstance(car, _TransportCar)


def test_assistant_runtime_builds_assistant_follow_runtime(monkeypatch) -> None:
    """辅车运行入口必须创建辅车角色运行时对象."""

    runtime_module = import_runtime_module("vision.assistant.runtime", monkeypatch)
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")

    class _TransportCar:
        def __init__(self) -> None:
            self.wheel_states = []
            self.imu = "imu"

        def mark_tick(self, _tick=None) -> None:
            return None

        def set_ticker(self, _ticker) -> None:
            return None

        def step(self) -> bool:
            return False

    monkeypatch.setitem(sys.modules, "core", core_package)
    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core.runtime", core_module)

    car = runtime_module.create_transport_car()

    assert car.__class__.__name__ == "AssistantFollowRuntime"
    assert not isinstance(car, _TransportCar)
    assert isinstance(car._transport_car, _TransportCar)
