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

    sys.modules.pop("config", None)
    sys.modules.pop("config.safety", None)
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


def test_main_entry_allocates_emergency_exception_buffer(monkeypatch) -> None:
    """入口加载时申请 MicroPython 中断异常缓冲。"""

    calls = []
    micropython_module = ModuleType("micropython")
    setattr(
        micropython_module,
        "alloc_emergency_exception_buf",
        lambda size: calls.append(size),
    )
    monkeypatch.setitem(sys.modules, "micropython", micropython_module)

    load_main_module()

    assert calls == [100]


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
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
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
    assert "[boot] main: power voltage=12.00V" in output_lines
    assert "[boot] main: startup keys=[0, 0, 0, 0]" in output_lines
    assert "[boot] main: selected script=script/remote_control.py" in output_lines
    assert "[boot] main: launching script=script/remote_control.py" in output_lines


def test_main_entry_catches_and_saves_fatal_errors(
    capsys, tmp_path, monkeypatch
) -> None:
    """正式入口必须兜住脚本运行期异常并保存到板端文件."""

    main = load_main_module()
    log_path = tmp_path / "last_fatal_error.log"

    monkeypatch.setattr(main, "FATAL_ERROR_LOG_PATH", str(log_path))
    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])

    def _raise_script(_script_path):
        raise RuntimeError("script boom")

    monkeypatch.setattr(main, "_run_script", _raise_script)

    result = main.main()
    output_lines = capsys.readouterr().out.splitlines()

    assert result is None
    assert "[boot] main: fatal error: script boom" in output_lines
    assert log_path.read_text() == "fatal error: script boom\n"


def test_main_entry_logs_when_fatal_error_save_fails(capsys, monkeypatch) -> None:
    """致命错误保存失败时, 入口仍要完成兜底日志输出."""

    main = load_main_module()

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])
    monkeypatch.setattr(
        main,
        "_run_script",
        lambda _script_path: (_ for _ in ()).throw(RuntimeError("script boom")),
    )
    monkeypatch.setattr(
        main,
        "_save_fatal_error_log",
        lambda _message: (_ for _ in ()).throw(OSError("flash full")),
    )

    result = main.main()
    output_lines = capsys.readouterr().out.splitlines()

    assert result is None
    assert "[boot] main: fatal error: script boom" in output_lines
    assert "[boot] main: fatal log save failed: flash full" in output_lines


def test_main_entry_blocks_script_when_voltage_is_low(capsys, monkeypatch) -> None:
    """入口阶段电压不足时只进入蜂鸣告警."""

    main = load_main_module()
    launched_scripts = []
    alarmed = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 11.4)
    monkeypatch.setattr(
        main,
        "_run_low_voltage_alarm",
        lambda voltage: alarmed.append(voltage) or "alarm",
    )
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])
    monkeypatch.setattr(
        main,
        "_run_script",
        lambda script_path: launched_scripts.append(script_path),
    )

    result = main.main()
    output_lines = capsys.readouterr().out.splitlines()

    assert result == "alarm"
    assert launched_scripts == []
    assert alarmed == [11.4]
    assert "[boot] main: low voltage=11.40V" in output_lines


def test_main_entry_uses_configured_voltage_threshold(monkeypatch) -> None:
    """入口阶段使用配置阈值判定低电压."""

    main = load_main_module()
    launched_scripts = []
    alarmed = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
    monkeypatch.setattr(main.safety_params, "POWER_MIN_VOLTAGE_V", 12.1)
    monkeypatch.setattr(
        main,
        "_run_low_voltage_alarm",
        lambda voltage: alarmed.append(voltage) or "alarm",
    )
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])
    monkeypatch.setattr(
        main,
        "_run_script",
        lambda script_path: launched_scripts.append(script_path),
    )

    assert main.main() == "alarm"
    assert launched_scripts == []
    assert alarmed == [12.0]


def test_convert_power_adc_to_voltage_uses_board_divider() -> None:
    """B27 电池分压按板端 demo 公式换算."""

    main = load_main_module()
    half_scale = 32768

    voltage = main._convert_power_adc_to_voltage(half_scale)
    expected = half_scale / 65535 * 3.3 * 11.0

    assert voltage == pytest.approx(expected)


def test_resolve_existing_startup_script_prefers_compiled_file(monkeypatch) -> None:
    """脚本分发在交叉编译部署后应使用存在的 .mpy 文件."""

    main = load_main_module()
    existing = {"script/remote_control.mpy"}

    monkeypatch.setattr(main, "_path_exists", lambda path: path in existing)

    assert (
        main.resolve_existing_startup_script("script/remote_control.py")
        == "script/remote_control.mpy"
    )


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
