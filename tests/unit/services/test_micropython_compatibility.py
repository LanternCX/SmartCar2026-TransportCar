"""MicroPython 运行时兼容性回归测试."""

import builtins
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


pytestmark = pytest.mark.unit


def _module_path(relative_path: str) -> Path:
    """返回仓库内模块文件绝对路径."""
    return Path(__file__).resolve().parents[3] / relative_path


def _install_vision_package() -> ModuleType:
    """确保 `vision` 包对象存在,便于手动装载模块."""
    package = sys.modules.get("vision")
    if package is None:
        package = ModuleType("vision")
        package.__path__ = [str(_module_path("src/vision"))]  # type: ignore[attr-defined]
        sys.modules["vision"] = package
    return package


def _load_module_from_path(module_name: str, file_path: Path) -> ModuleType:
    """从给定文件路径显式装载模块."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _block_typing_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟板端不存在 `typing` 模块的运行环境."""
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "typing":
            raise ModuleNotFoundError("no module named 'typing'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def _block_types_import(monkeypatch: pytest.MonkeyPatch):
    """模拟板端不存在 `types` 模块的运行环境."""
    original_import = builtins.__import__
    previous_module = sys.modules.pop("types", None)

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "types":
            raise ModuleNotFoundError("no module named 'types'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    return previous_module


def _install_transport_stubs() -> None:
    """为 `services.car` 装载提供最小硬件桩模块."""
    machine = ModuleType("machine")

    class Pin:
        OUT = 0
        IN = 1
        PULL_UP_47K = 2

        def __init__(self, *_args, **_kwargs):
            self._value = 1

        def value(self):
            return self._value

        def toggle(self):
            return None

    class UART:
        def __init__(self, *_args, **_kwargs):
            self.messages = []

        def init(self, *_args, **_kwargs):
            return None

        def write(self, text):
            self.messages.append(text)

        def any(self):
            return 0

        def read(self, _size):
            return b""

    setattr(machine, "Pin", Pin)
    setattr(machine, "UART", UART)
    sys.modules["machine"] = machine

    seekfree = ModuleType("seekfree")

    class MOTOR_CONTROLLER:
        PWM_C30_DIR_C31 = 1
        PWM_D4_DIR_D5 = 2
        PWM_D6_DIR_D7 = 3

        def __init__(self, *_args, **_kwargs):
            self.last_duty = 0

        def duty(self, value):
            self.last_duty = value

    class IMU660RX:
        def get(self):
            return [0, 0, 0, 0, 0, 0]

    setattr(seekfree, "MOTOR_CONTROLLER", MOTOR_CONTROLLER)
    setattr(seekfree, "IMU660RX", IMU660RX)
    sys.modules["seekfree"] = seekfree

    smartcar = ModuleType("smartcar")

    class FakeEncoder:
        def get(self):
            return 0

    def encoder(*_args, **_kwargs):
        return FakeEncoder()

    setattr(smartcar, "encoder", encoder)
    sys.modules["smartcar"] = smartcar


def test_vision_protocol_module_loads_without_typing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_typing_import(monkeypatch)
    vision_pkg = _install_vision_package()

    previous_module = sys.modules.pop("vision.protocol", None)
    try:
        module = _load_module_from_path(
            "vision.protocol",
            _module_path("src/vision/protocol/__init__.py"),
        )
        setattr(vision_pkg, "protocol", module)
        assert hasattr(module, "VisionProtocol")
    finally:
        if previous_module is not None:
            sys.modules["vision.protocol"] = previous_module
            setattr(vision_pkg, "protocol", previous_module)
        else:
            sys.modules.pop("vision.protocol", None)
            if hasattr(vision_pkg, "protocol"):
                delattr(vision_pkg, "protocol")


def test_vision_state_machine_module_loads_without_typing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_typing_import(monkeypatch)
    vision_pkg = _install_vision_package()

    previous_protocol = sys.modules.pop("vision.protocol", None)
    previous_machine = sys.modules.pop("vision.state_machine", None)
    try:
        protocol_module = _load_module_from_path(
            "vision.protocol",
            _module_path("src/vision/protocol/__init__.py"),
        )
        setattr(vision_pkg, "protocol", protocol_module)
        module = _load_module_from_path(
            "vision.state_machine",
            _module_path("src/vision/state_machine/__init__.py"),
        )
        setattr(vision_pkg, "state_machine", module)
        assert hasattr(module, "VisionStateMachine")
    finally:
        if previous_protocol is not None:
            sys.modules["vision.protocol"] = previous_protocol
            setattr(vision_pkg, "protocol", previous_protocol)
        else:
            sys.modules.pop("vision.protocol", None)
            if hasattr(vision_pkg, "protocol"):
                delattr(vision_pkg, "protocol")

        if previous_machine is not None:
            sys.modules["vision.state_machine"] = previous_machine
            setattr(vision_pkg, "state_machine", previous_machine)
        else:
            sys.modules.pop("vision.state_machine", None)
            if hasattr(vision_pkg, "state_machine"):
                delattr(vision_pkg, "state_machine")


def test_services_car_vision_module_loads_without_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    previous_types = _block_types_import(monkeypatch)
    previous_module = sys.modules.pop("services.car.vision", None)
    previous_car_package = sys.modules.pop("services.car", None)

    try:
        module = _load_module_from_path(
            "services.car.vision",
            _module_path("src/services/car/vision.py"),
        )
        assert hasattr(module, "VisionMixin")
    finally:
        if previous_types is not None:
            sys.modules["types"] = previous_types
        if previous_module is not None:
            sys.modules["services.car.vision"] = previous_module
        else:
            sys.modules.pop("services.car.vision", None)
        if previous_car_package is not None:
            sys.modules["services.car"] = previous_car_package
        else:
            sys.modules.pop("services.car", None)
