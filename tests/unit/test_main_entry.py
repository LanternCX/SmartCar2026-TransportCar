"""`main.py` 入口约束测试.

@file tests/unit/test_main_entry.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def test_main_entry_exists() -> None:
    """当前正式入口必须切到 `src/main.py`."""

    assert MAIN_PATH.exists()


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


def test_main_entry_source_uses_key_handler_and_avoids_role_switch_pins() -> None:
    """脚本分发必须基于 KEY_HANDLER, 不能回到 D8/D9."""

    source = MAIN_PATH.read_text(encoding="utf-8")

    assert "KEY_HANDLER" in source
    assert '"D8"' not in source
    assert '"D9"' not in source


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
