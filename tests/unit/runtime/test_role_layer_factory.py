"""角色运行入口装配约束测试.

@file tests/unit/runtime/test_role_layer_factory.py
"""

from importlib import import_module
from pathlib import Path
from types import ModuleType
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


def import_role_package(monkeypatch):
    """按正常包路径导入角色运行入口装配入口."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for module_name in (
        "role",
        "role.master",
        "role.master.runtime",
        "role.assistant",
        "role.assistant.runtime",
    ):
        sys.modules.pop(module_name, None)
    return import_module("role")


def import_runtime_module(module_name, monkeypatch):
    """按正常包路径导入指定角色运行模块."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for loaded_name in (
        "config",
        "config.motion",
        "config.storage",
        "storage.param_manager",
    ):
        sys.modules.pop(loaded_name, None)
    sys.modules.pop(module_name, None)
    return import_module(module_name)


def test_create_role_transport_car_selects_master_branch_only(monkeypatch) -> None:
    """主车装配只能触发主车角色运行分支."""

    role_runtime = import_role_package(monkeypatch)
    calls = []

    master_module = ModuleType("role.master")
    setattr(
        master_module,
        "create_transport_car",
        lambda: calls.append("master") or {"role": "master"},
    )

    assistant_module = ModuleType("role.assistant")

    def fail_assistant_create_transport_car():
        raise AssertionError("assistant branch should not be loaded")

    setattr(
        assistant_module,
        "create_transport_car",
        fail_assistant_create_transport_car,
    )

    monkeypatch.setitem(sys.modules, "role.master", master_module)
    monkeypatch.setitem(sys.modules, "role.assistant", assistant_module)

    layer = role_runtime.create_role_transport_car("master")

    assert layer == {"role": "master"}
    assert calls == ["master"]


def test_create_role_transport_car_selects_assistant_branch_only(monkeypatch) -> None:
    """辅车装配只能触发辅车角色运行分支."""

    role_runtime = import_role_package(monkeypatch)
    calls = []

    master_module = ModuleType("role.master")

    def fail_master_create_transport_car():
        raise AssertionError("master branch should not be loaded")

    setattr(
        master_module,
        "create_transport_car",
        fail_master_create_transport_car,
    )

    assistant_module = ModuleType("role.assistant")
    setattr(
        assistant_module,
        "create_transport_car",
        lambda: calls.append("assistant") or {"role": "assistant"},
    )

    monkeypatch.setitem(sys.modules, "role.master", master_module)
    monkeypatch.setitem(sys.modules, "role.assistant", assistant_module)

    layer = role_runtime.create_role_transport_car("assistant")

    assert layer == {"role": "assistant"}
    assert calls == ["assistant"]


def test_create_role_transport_car_rejects_unknown_role(monkeypatch) -> None:
    """未知角色必须被拒绝, 不能偷偷回默认分支."""

    role_runtime = import_role_package(monkeypatch)

    with pytest.raises(ValueError):
        role_runtime.create_role_transport_car("unknown")


def test_master_runtime_builds_master_forward_runtime(monkeypatch) -> None:
    """主车运行入口必须创建主车角色运行时对象."""

    runtime_module = import_runtime_module("role.master.runtime", monkeypatch)
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")
    created_roles = []

    class _TransportCar:
        def __init__(self, vehicle_role=None) -> None:
            created_roles.append(vehicle_role)
            self.wheel_encoders = ("enc_m",)
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
    param_manager = import_module("storage.param_manager")
    monkeypatch.setattr(
        param_manager,
        "load_obstacle_slots",
        lambda _path, _field_size: ((None, -1.0, -1.0),) * 3,
        raising=False,
    )

    car = runtime_module.create_transport_car()

    assert not isinstance(car, _TransportCar)
    assert car.wheel_encoders == ("enc_m",)
    assert car.imu == "imu"
    assert hasattr(car, "step")
    assert created_roles == ["master"]


def test_master_runtime_loads_obstacles_once_before_forward_runtime(monkeypatch) -> None:
    """主车正式装配只加载一次障碍配置并显式传给运行流程."""
    runtime_module = import_runtime_module("role.master.runtime", monkeypatch)
    slots = (("top", 1.45, 1.75), (None, -1.0, -1.0), (None, -1.0, -1.0))
    load_calls = []
    received = []

    param_manager = import_module("storage.param_manager")

    def _load(path, field_size):
        load_calls.append((path, field_size))
        return slots

    monkeypatch.setattr(param_manager, "load_obstacle_slots", _load, raising=False)
    forward_module = ModuleType("role.master.forward_runtime")
    setattr(
        forward_module,
        "MasterForwardRuntime",
        lambda obstacle_slots: received.append(obstacle_slots) or object(),
    )
    monkeypatch.setitem(sys.modules, "role.master.forward_runtime", forward_module)

    runtime_module.create_transport_car()

    assert len(load_calls) == 1
    assert received == [slots]


def test_master_runtime_stops_when_obstacle_loading_fails(monkeypatch) -> None:
    """障碍文件读取失败时不创建主车运行流程."""
    runtime_module = import_runtime_module("role.master.runtime", monkeypatch)
    param_manager = import_module("storage.param_manager")
    monkeypatch.setattr(
        param_manager,
        "load_obstacle_slots",
        lambda _path, _field_size: (_ for _ in ()).throw(ValueError()),
        raising=False,
    )
    forward_module = ModuleType("role.master.forward_runtime")
    setattr(
        forward_module,
        "MasterForwardRuntime",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("forward runtime must not be created")
        ),
    )
    monkeypatch.setitem(sys.modules, "role.master.forward_runtime", forward_module)

    with pytest.raises(ValueError):
        runtime_module.create_transport_car()


def test_assistant_runtime_builds_assistant_follow_runtime(monkeypatch) -> None:
    """辅车运行入口必须创建辅车角色运行时对象."""

    runtime_module = import_runtime_module("role.assistant.runtime", monkeypatch)
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")
    created_roles = []

    class _TransportCar:
        def __init__(self, vehicle_role=None) -> None:
            created_roles.append(vehicle_role)
            self.wheel_encoders = ("enc_m",)
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
    param_manager = import_module("storage.param_manager")
    monkeypatch.setattr(
        param_manager,
        "load_obstacle_slots",
        lambda _path, _field_size: ((None, -1.0, -1.0),) * 3,
        raising=False,
    )

    car = runtime_module.create_transport_car()

    assert not isinstance(car, _TransportCar)
    assert car.wheel_encoders == ("enc_m",)
    assert car.imu == "imu"
    assert hasattr(car, "step")
    assert created_roles == ["assistant"]


def test_assistant_runtime_loads_obstacles_once_before_follow_runtime(monkeypatch) -> None:
    """辅车正式装配只加载一次障碍配置并显式传给运行流程."""
    runtime_module = import_runtime_module("role.assistant.runtime", monkeypatch)
    slots = (("right", 1.45, 1.75), (None, -1.0, -1.0), (None, -1.0, -1.0))
    load_calls = []
    received = []

    param_manager = import_module("storage.param_manager")

    def _load(path, field_size):
        load_calls.append((path, field_size))
        return slots

    monkeypatch.setattr(param_manager, "load_obstacle_slots", _load, raising=False)
    follow_module = ModuleType("role.assistant.follow_runtime")
    setattr(
        follow_module,
        "AssistantFollowRuntime",
        lambda obstacle_slots: received.append(obstacle_slots) or object(),
    )
    monkeypatch.setitem(sys.modules, "role.assistant.follow_runtime", follow_module)

    runtime_module.create_transport_car()

    assert len(load_calls) == 1
    assert received == [slots]


def test_assistant_runtime_stops_when_obstacle_loading_fails(monkeypatch) -> None:
    """辅车障碍文件读取失败时不创建运行流程."""
    runtime_module = import_runtime_module("role.assistant.runtime", monkeypatch)
    param_manager = import_module("storage.param_manager")
    monkeypatch.setattr(
        param_manager,
        "load_obstacle_slots",
        lambda _path, _field_size: (_ for _ in ()).throw(ValueError()),
        raising=False,
    )
    follow_module = ModuleType("role.assistant.follow_runtime")
    setattr(
        follow_module,
        "AssistantFollowRuntime",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("follow runtime must not be created")
        ),
    )
    monkeypatch.setitem(sys.modules, "role.assistant.follow_runtime", follow_module)

    with pytest.raises(ValueError):
        runtime_module.create_transport_car()
