"""`main.py` 入口约束测试.

@file tests/unit/test_main_entry.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_PATH = PROJECT_ROOT / "src" / "main.py"


def load_main_module():
    """按文件路径加载入口模块."""

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
