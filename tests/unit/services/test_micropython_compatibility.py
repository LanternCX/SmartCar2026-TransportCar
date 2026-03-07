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


def _install_services_package() -> ModuleType:
    """确保 `services` 包对象存在,便于手动装载模块."""
    package = sys.modules.get("services")
    if package is None:
        package = ModuleType("services")
        package.__path__ = []  # type: ignore[attr-defined]
        sys.modules["services"] = package
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


def test_vision_protocol_module_loads_without_typing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_typing_import(monkeypatch)
    services_pkg = _install_services_package()

    previous_module = sys.modules.pop("services.vision_protocol", None)
    try:
        module = _load_module_from_path(
            "services.vision_protocol",
            _module_path("src/services/vision_protocol.py"),
        )
        setattr(services_pkg, "vision_protocol", module)
        assert hasattr(module, "VisionProtocol")
    finally:
        if previous_module is not None:
            sys.modules["services.vision_protocol"] = previous_module
            setattr(services_pkg, "vision_protocol", previous_module)
        else:
            sys.modules.pop("services.vision_protocol", None)
            if hasattr(services_pkg, "vision_protocol"):
                delattr(services_pkg, "vision_protocol")


def test_vision_state_machine_module_loads_without_typing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_typing_import(monkeypatch)
    services_pkg = _install_services_package()

    previous_protocol = sys.modules.pop("services.vision_protocol", None)
    previous_machine = sys.modules.pop("services.vision_state_machine", None)
    try:
        protocol_module = _load_module_from_path(
            "services.vision_protocol",
            _module_path("src/services/vision_protocol.py"),
        )
        setattr(services_pkg, "vision_protocol", protocol_module)
        module = _load_module_from_path(
            "services.vision_state_machine",
            _module_path("src/services/vision_state_machine.py"),
        )
        setattr(services_pkg, "vision_state_machine", module)
        assert hasattr(module, "VisionStateMachine")
    finally:
        if previous_protocol is not None:
            sys.modules["services.vision_protocol"] = previous_protocol
            setattr(services_pkg, "vision_protocol", previous_protocol)
        else:
            sys.modules.pop("services.vision_protocol", None)
            if hasattr(services_pkg, "vision_protocol"):
                delattr(services_pkg, "vision_protocol")

        if previous_machine is not None:
            sys.modules["services.vision_state_machine"] = previous_machine
            setattr(services_pkg, "vision_state_machine", previous_machine)
        else:
            sys.modules.pop("services.vision_state_machine", None)
            if hasattr(services_pkg, "vision_state_machine"):
                delattr(services_pkg, "vision_state_machine")
