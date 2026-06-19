"""`main.py` 入口约束测试.

@file tests/unit/entry/test_main_entry.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import builtins
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "src" / "main.py"


def load_main_module():
    """按文件路径加载入口模块."""

    sys.modules.pop("config", None)
    sys.modules.pop("config.safety", None)
    sys.modules.pop("config.startup", None)
    sys.modules.pop("utils.startup_log", None)
    spec = spec_from_file_location("transport_main_entry", MAIN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_startup_role(monkeypatch, main, role="assistant") -> None:
    """指定入口测试使用的车辆角色."""

    monkeypatch.setattr(main, "_read_startup_vehicle_role", lambda: role)


def test_resolve_startup_script_uses_long_press_only() -> None:
    """只有长按才触发维护脚本."""

    main = load_main_module()
    main.startup_params.STARTUP_TEST_MODE = False

    assert main.resolve_startup_script([1, 0, 0, 0]) == "script/remote_control.py"
    assert main.resolve_startup_script([0, 1, 0, 0]) == "script/remote_control.py"
    assert main.resolve_startup_script([0, 0, 2, 0]) == "script/pid_identify.py"
    assert main.resolve_startup_script([0, 0, 0, 2]) == "script/calibrate_gyro.py"


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


def test_main_entry_binds_uart3_to_repl_before_startup_logs(
    capsys, monkeypatch
) -> None:
    """正式入口启动时必须先把 UART3 交给 REPL."""

    main = load_main_module()
    events = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main)
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])
    monkeypatch.setattr(main, "_run_script", lambda _script_path: None)
    monkeypatch.setattr(
        main,
        "log",
        lambda stage, detail="": events.append(("log", stage, detail)),
    )
    monkeypatch.setattr(main, "_bind_uart3_repl", lambda: events.append("repl"))

    main.main()

    assert events[0] == "repl"


def test_resolve_startup_script_defaults_to_remote_control() -> None:
    """没有长按时进入默认运行脚本."""

    main = load_main_module()
    main.startup_params.STARTUP_TEST_MODE = False

    assert main.resolve_startup_script([0, 0, 0, 0]) == "script/remote_control.py"


def test_resolve_startup_script_uses_test_entry_when_config_enabled() -> None:
    """配置开启测试模式时进入测试入口."""

    main = load_main_module()

    main.startup_params.STARTUP_TEST_MODE = True

    assert main.resolve_startup_script([0, 0, 0, 0]) == "script/test.py"


def test_resolve_startup_script_rejects_dual_long_press() -> None:
    """两个维护按键同时长按时必须拒绝进入正常脚本."""

    main = load_main_module()

    with pytest.raises(ValueError):
        main.resolve_startup_script([0, 0, 2, 2])


def test_main_entry_logs_startup_stages(capsys, monkeypatch) -> None:
    """入口阶段必须输出关键启动日志, 便于定位卡住位置."""

    main = load_main_module()
    main.startup_params.STARTUP_TEST_MODE = False
    launched_scripts = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main)
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
    assert any(line.endswith("main: entry start") for line in output_lines)
    assert any(line.endswith("main: power voltage=12.00V") for line in output_lines)
    assert any(line.endswith("main: startup keys=[0, 0, 0, 0]") for line in output_lines)
    assert any(
        line.endswith("main: selected script=script/remote_control.py")
        for line in output_lines
    )
    assert any(
        line.endswith("main: launching script=script/remote_control.py")
        for line in output_lines
    )


def test_main_entry_prints_full_fatal_trace_and_memory_snapshot(
    capsys, monkeypatch
) -> None:
    """正式入口发生致命异常时必须输出完整异常类型、调用链和内存快照."""

    main = load_main_module()
    trace_calls = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main)
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])

    def _raise_script(_script_path):
        raise MemoryError("memory allocation failed, allocating 1524 bytes")

    monkeypatch.setattr(main, "_run_script", _raise_script)
    monkeypatch.setattr(main, "_save_fatal_exception_log", lambda _message, _exc: None)
    monkeypatch.setattr(
        sys,
        "print_exception",
        lambda exc, file=None: (
            trace_calls.append((type(exc).__name__, file)),
            print(
                "Traceback (most recent call last):\n  File \"script/remote_control.py\", line 1, in main\nMemoryError: %s"
                % exc,
                file=file,
            ),
        )[-1],
        raising=False,
    )

    gc_module = ModuleType("gc")
    setattr(gc_module, "mem_free", lambda: 4096)
    setattr(gc_module, "mem_alloc", lambda: 2048)
    monkeypatch.setitem(sys.modules, "gc", gc_module)

    result = main.main()
    output = capsys.readouterr().out

    assert result is None
    assert "main: fatal error: memory allocation failed, allocating 1524 bytes" in output
    assert "main: fatal error type=MemoryError" in output
    assert "main: fatal mem_free=4096 mem_alloc=2048" in output
    assert "Traceback (most recent call last):" in output
    assert "MemoryError: memory allocation failed, allocating 1524 bytes" in output
    assert trace_calls


def test_main_entry_logs_when_fatal_error_save_fails(capsys, monkeypatch) -> None:
    """致命错误保存失败时, 入口仍要完成兜底日志输出."""

    main = load_main_module()

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main)
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])
    monkeypatch.setattr(
        main,
        "_run_script",
        lambda _script_path: (_ for _ in ()).throw(RuntimeError("script boom")),
    )
    monkeypatch.setattr(
        main,
        "_save_fatal_exception_log",
        lambda _message, _exc: (_ for _ in ()).throw(OSError("flash full")),
    )
    trace_calls = []
    monkeypatch.setattr(
        main,
        "log_exception",
        lambda stage, detail, exc: trace_calls.append((stage, detail, str(exc))),
        raising=False,
    )

    result = main.main()
    output_lines = capsys.readouterr().out.splitlines()

    assert result is None
    assert any(line.endswith("main: fatal error: script boom") for line in output_lines)
    assert trace_calls == [("main", "fatal log save failed: flash full", "flash full")]


def test_main_entry_blocks_assistant_script_when_voltage_is_low(
    capsys, monkeypatch
) -> None:
    """辅车入口阶段电压不足时只进入蜂鸣告警."""

    main = load_main_module()
    launched_scripts = []
    alarmed = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main, "assistant")
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 3.6)
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
    assert alarmed == [3.6]
    assert any(line.endswith("main: low voltage=3.60V") for line in output_lines)


def test_main_entry_blocks_master_script_with_master_voltage_threshold(
    capsys, monkeypatch
) -> None:
    """主车入口阶段按 11.5V 阈值保护."""

    main = load_main_module()
    launched_scripts = []
    alarmed = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main, "master")
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
    assert any(line.endswith("main: low voltage=11.40V") for line in output_lines)


def test_main_entry_allows_assistant_script_above_assistant_voltage_threshold(
    monkeypatch,
) -> None:
    """辅车入口阶段不使用主车 11.5V 阈值."""

    main = load_main_module()
    launched_scripts = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main, "assistant")
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 11.4)
    monkeypatch.setattr(main, "_scan_startup_key_states", lambda: [0, 0, 0, 0])
    monkeypatch.setattr(
        main,
        "_run_script",
        lambda script_path: launched_scripts.append(script_path),
    )

    assert main.main() == "script/remote_control.py"
    assert launched_scripts == ["script/remote_control.py"]


def test_main_entry_uses_configured_voltage_threshold(monkeypatch) -> None:
    """入口阶段使用配置阈值判定低电压."""

    main = load_main_module()
    launched_scripts = []
    alarmed = []

    monkeypatch.setattr(main, "_sleep_ms", lambda _delay_ms: None)
    _set_startup_role(monkeypatch, main, "master")
    monkeypatch.setattr(main, "_read_startup_voltage", lambda: 12.0)
    monkeypatch.setattr(main.safety_params, "MASTER_POWER_MIN_VOLTAGE_V", 12.1)
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


def test_resolve_existing_startup_script_keeps_test_entry_source(monkeypatch) -> None:
    """板端测试入口使用源码文件, 避免旧编译产物遮蔽调试脚本."""

    main = load_main_module()
    existing = {"script/test.mpy"}

    monkeypatch.setattr(main, "_path_exists", lambda path: path in existing)

    assert main.resolve_existing_startup_script("script/test.py") == "script/test.py"


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


def test_run_python_script_uses_global_execfile(monkeypatch) -> None:
    """普通脚本必须通过板端全局脚本执行能力运行."""

    main = load_main_module()
    calls = []
    setattr(
        builtins,
        "execfile",
        lambda script_path: calls.append(("execfile", script_path)) or "ok",
    )
    monkeypatch.setattr(main, "_chdir_flash", lambda: calls.append(("chdir", None)))

    try:
        assert main._run_script("script/remote_control.py") == "ok"
        assert calls == [
            ("chdir", None),
            ("execfile", "script/remote_control.py"),
        ]
    finally:
        delattr(builtins, "execfile")
