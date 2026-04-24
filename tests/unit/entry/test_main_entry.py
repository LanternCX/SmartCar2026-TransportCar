"""`main.py` 入口约束测试.

@file tests/unit/entry/test_main_entry.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "src" / "main.py"


def load_main_module():
    """按文件路径加载入口模块."""

    sys.modules.pop("utils.startup_log", None)
    spec = spec_from_file_location("transport_main_entry", MAIN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_startup_script_uses_long_press_only() -> None:
    """只有长按才触发维护脚本."""

    main = load_main_module()

    assert main.resolve_startup_script([1, 0, 0, 0]) == "script/remote_control.py"
    assert main.resolve_startup_script([0, 1, 0, 0]) == "script/remote_control.py"
    assert main.resolve_startup_script([2, 0, 0, 0]) == "script/pid_identify.py"
    assert main.resolve_startup_script([0, 2, 0, 0]) == "script/calibrate_gyro.py"


def test_resolve_startup_script_defaults_to_remote_control() -> None:
    """没有长按时进入默认运行脚本."""

    main = load_main_module()

    assert main.resolve_startup_script([0, 0, 0, 0]) == "script/remote_control.py"


def test_resolve_startup_script_rejects_dual_long_press() -> None:
    """两个维护按键同时长按时必须拒绝进入正常脚本."""

    main = load_main_module()

    with pytest.raises(ValueError):
        main.resolve_startup_script([2, 2, 0, 0])


def test_main_entry_logs_startup_stages(capsys, monkeypatch) -> None:
    """入口阶段必须输出关键启动日志, 便于定位卡住位置."""

    main = load_main_module()
    launched_scripts = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])
    monkeypatch.setattr(
        main,
        "_run_script",
        lambda script_path: launched_scripts.append(script_path),
    )

    result = main.main()
    output_lines = capsys.readouterr().out.splitlines()

    assert result == "script/remote_control.py"
    assert launched_scripts == ["script/remote_control.py"]
    assert "[boot] main: entry start" in output_lines
    assert "[boot] main: startup keys=[0, 0, 0, 0]" in output_lines
    assert "[boot] main: selected script=script/remote_control.py" in output_lines
    assert "[boot] main: launching script=script/remote_control.py" in output_lines


def test_resolve_existing_startup_script_prefers_compiled_file(monkeypatch) -> None:
    """脚本分发在交叉编译部署后应使用存在的 .mpy 文件."""

    main = load_main_module()
    existing = {"script/remote_control.mpy"}

    monkeypatch.setattr(main, "_path_exists", lambda path: path in existing)

    assert (
        main.resolve_existing_startup_script("script/remote_control.py")
        == "script/remote_control.mpy"
    )


def test_command_autodiscover_accepts_mpy_suffix(tmp_path, monkeypatch) -> None:
    """命令包在只存在 .mpy 文件时仍能自动发现."""

    import importlib
    import builtins

    package_root = tmp_path / "command" / "commands"
    package_root.mkdir(parents=True)
    commands_init_path = PROJECT_ROOT / "src" / "command" / "commands" / "__init__.py"
    init_source = commands_init_path.read_text(encoding="utf-8")
    (tmp_path / "command" / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "__init__.py").write_text(init_source, encoding="utf-8")
    (package_root / "cmd_demo.mpy").write_text("", encoding="utf-8")
    imported = []
    real_import = builtins.__import__

    def recording_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "command.commands.cmd_demo":
            imported.append(name)
            return object()
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(builtins, "__import__", recording_import)
    sys.modules.pop("command", None)
    sys.modules.pop("command.commands", None)

    importlib.import_module("command.commands")

    assert "command.commands.cmd_demo" in imported


def test_run_compiled_script_imports_module_and_calls_main(monkeypatch) -> None:
    """编译后的启动脚本必须通过模块导入执行."""

    main = load_main_module()
    calls = []

    class FakeModule:
        def main(self):
            calls.append("main-called")
            return "ok"

    monkeypatch.setattr(main, "_chdir_flash", lambda: calls.append("chdir"))
    monkeypatch.setattr(
        main,
        "_import_module",
        lambda module_name: calls.append(module_name) or FakeModule(),
    )

    assert main._run_script("script/remote_control.mpy") == "ok"
    assert calls == ["chdir", "script.remote_control", "main-called"]
