import importlib.util
from pathlib import Path
import sys

import pytest


RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "src" / "assistant"
SRC_ROOT = RUNTIME_ROOT.parent
RUNTIME_MODULES = {
    "app",
    "config",
    "main",
    "motion_runtime",
    "protocol",
    "runtime_params",
    "safety",
    "status",
}
RUNTIME_PACKAGES = {"ctrl", "hw", "script", "stability"}


def _clear_assistant_runtime_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "assistant" or module_name.startswith("assistant."):
            sys.modules.pop(module_name, None)
            continue
        if module_name in RUNTIME_MODULES:
            sys.modules.pop(module_name, None)
            continue
        if module_name.split(".", 1)[0] in RUNTIME_PACKAGES:
            sys.modules.pop(module_name, None)


def _load_runtime_file(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, RUNTIME_ROOT / file_name)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _prepare_assistant_runtime_imports(monkeypatch):
    _clear_assistant_runtime_modules()
    monkeypatch.syspath_prepend(str(SRC_ROOT))
    monkeypatch.syspath_prepend(str(RUNTIME_ROOT))
    yield
    _clear_assistant_runtime_modules()


def _build_fake_hw_bundle() -> dict:
    class FakeMotor:
        def __init__(self) -> None:
            self.last_duty = 0

        def set_duty(self, duty) -> None:
            self.last_duty = int(duty)

        def stop(self) -> None:
            self.last_duty = 0

    return {
        "uart": {"uart3": object()},
        "motors": {
            "m": FakeMotor(),
            "l": FakeMotor(),
            "r": FakeMotor(),
        },
        "encoders": {"rear_left": object()},
        "imu": object(),
    }


def test_assistant_main_starts_runtime_when_no_button_is_held(monkeypatch) -> None:
    from assistant.main import main

    started = {"count": 0}

    def _start_runtime() -> None:
        started["count"] += 1

    monkeypatch.setattr("assistant.main._read_button_state", lambda pin: False)
    monkeypatch.setattr("assistant.main._start_runtime", _start_runtime)
    main()

    assert started["count"] == 1


def test_assistant_read_button_state_propagates_import_error(monkeypatch) -> None:
    import builtins
    import pytest

    from assistant.main import _read_button_state

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "machine":
            raise ImportError("缺少 machine 模块")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(ImportError, match="缺少 machine 模块"):
        _read_button_state("C8")


def test_assistant_read_now_ms_propagates_import_error(monkeypatch) -> None:
    import builtins
    import pytest

    from assistant.main import _read_now_ms

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "time":
            raise ImportError("缺少 time 模块")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(ImportError, match="缺少 time 模块"):
        _read_now_ms()


def test_assistant_main_supports_device_root_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "path",
        [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != SRC_ROOT.resolve()
        ],
    )

    module = _load_runtime_file("__main__", "main.py")

    assert callable(module.main)
    assert callable(module.build_hw_bundle)


def test_assistant_app_supports_device_root_import(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "path",
        [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != SRC_ROOT.resolve()
        ],
    )

    module = _load_runtime_file("app", "app.py")

    assert callable(module.build_hw_bundle)
    assert module.AssistantRuntimeLoop is not None


def test_assistant_build_hw_bundle_keeps_legacy_encoder_mapping() -> None:
    from assistant.app import build_hw_bundle

    hw_bundle = build_hw_bundle()
    encoder_pins = {
        name: (port.phase_a_pin, port.phase_b_pin, port.invert)
        for name, port in hw_bundle["encoders"].items()
    }

    assert encoder_pins == {
        "m": ("D15", "D16", True),
        "l": ("C0", "C1", True),
        "r": ("C2", "C3", True),
    }


def test_assistant_build_hw_bundle_supports_package_only_import(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "path",
        [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != RUNTIME_ROOT.resolve()
        ],
    )

    from assistant.app import build_hw_bundle

    hw_bundle = build_hw_bundle()

    assert set(hw_bundle["uart"]) == {"uart3"}


def test_assistant_ctrl_chassis_supports_package_import(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "path",
        [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != RUNTIME_ROOT.resolve()
        ],
    )

    import assistant.ctrl.chassis as module

    assert module.ChassisRuntime is not None


def test_assistant_runtime_loop_uses_same_full_hw_bundle_owner() -> None:
    from assistant.app import AssistantRuntimeLoop

    hw_bundle = {
        "uart": {"uart3": object()},
        "motors": {"m": object()},
        "encoders": {"rear_left": object()},
        "imu": object(),
    }

    loop = AssistantRuntimeLoop(hw_bundle)

    assert loop.hw_bundle is hw_bundle
    assert loop.app.hw_bundle is hw_bundle


def test_assistant_main_import_does_not_load_script_modules(monkeypatch) -> None:
    import builtins
    import importlib

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "script.calibrate_gyro" or name == "script.pid_identify":
            raise AssertionError("主机侧导入 main 时不应拉起脚本模块")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    module = importlib.import_module("assistant.main")

    assert callable(module.main)


def test_assistant_main_dispatches_calibrate_gyro_when_c9_is_held(monkeypatch) -> None:
    from assistant.main import main

    called = {"calibrate": 0}

    def _run_calibrate_gyro() -> None:
        called["calibrate"] += 1

    monkeypatch.setattr("assistant.main._read_button_state", lambda pin: pin == "C9")
    monkeypatch.setattr("assistant.main.run_calibrate_gyro", _run_calibrate_gyro)
    main()

    assert called["calibrate"] == 1


def test_assistant_main_dispatches_pid_identify_when_c8_is_held(monkeypatch) -> None:
    from assistant.main import main

    called = {"pid": 0}

    def _run_pid_identify() -> None:
        called["pid"] += 1

    monkeypatch.setattr("assistant.main._read_button_state", lambda pin: pin == "C8")
    monkeypatch.setattr("assistant.main.run_pid_identify", _run_pid_identify)
    main()

    assert called["pid"] == 1


def test_assistant_start_runtime_builds_loop_and_hands_it_to_driver(
    monkeypatch,
) -> None:
    from assistant.main import _start_runtime

    captured = {"drive_loop": None}
    uart3 = object()
    motors = {"m": object()}
    hw_bundle = {
        "uart": {"uart3": uart3},
        "motors": motors,
        "encoders": {"rear_left": object()},
        "imu": object(),
    }

    class DummyLoop:
        pass

    def _loop_factory(loop_bundle):
        captured["loop_bundle"] = loop_bundle
        return DummyLoop()

    def _drive_loop(loop) -> None:
        captured["drive_loop"] = loop

    monkeypatch.setattr("assistant.main.AssistantRuntimeLoop", _loop_factory)
    monkeypatch.setattr("assistant.main.build_hw_bundle", lambda: hw_bundle)
    monkeypatch.setattr("assistant.main._drive_loop", _drive_loop)
    _start_runtime()

    loop_bundle = captured["loop_bundle"]

    assert loop_bundle is not None
    assert loop_bundle is hw_bundle
    assert set(loop_bundle.keys()) == {"uart", "motors", "encoders", "imu"}
    assert isinstance(captured["drive_loop"], DummyLoop)


def test_assistant_drive_loop_waits_for_next_5ms_tick(monkeypatch) -> None:
    import pytest

    from assistant.main import _drive_loop

    step_calls = []
    sleep_calls = []
    now_values = iter((200, 200, 203, 205, 205))

    class DummyLoop:
        def step(self, now_ms):
            step_calls.append(now_ms)
            if len(step_calls) == 2:
                raise SystemExit(0)

    monkeypatch.setattr("assistant.main._read_now_ms", lambda: next(now_values))
    monkeypatch.setattr(
        "assistant.main._sleep_ms", lambda delay_ms: sleep_calls.append(delay_ms)
    )

    with pytest.raises(SystemExit) as exc_info:
        _drive_loop(DummyLoop())

    assert exc_info.value.code == 0
    assert step_calls == [200, 205]
    assert sleep_calls == [5, 2]


def test_assistant_app_handles_ping_and_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    assert app.handle_line("PING", now_ms=0) == "ACK,last_seq=0"
    state = app.handle_line("STATE?", now_ms=1)

    assert state.startswith("state=1,")


def test_assistant_app_maps_auxiliary_entries_to_ack_with_last_seq() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)

    hold_reply = app.handle_line("HOLD", now_ms=11)
    stop_reply = app.handle_line("STOP", now_ms=12)
    reset_reply = app.handle_line("RESET_ODOM", now_ms=13)

    assert hold_reply == "ACK,last_seq=8"
    assert stop_reply == "ACK,last_seq=8"
    assert reset_reply == "ACK,last_seq=8"


def test_assistant_app_keeps_follow_phase_silent_but_reports_timeout() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    follow_reply = app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)
    busy_tick_reply = app.tick(now_ms=50)
    timeout_reply = app.tick(now_ms=120)

    assert follow_reply == ""
    assert busy_tick_reply == ""
    assert timeout_reply == "TIMEOUT,last_seq=8"


def test_assistant_app_reports_timeout_only_once_until_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)

    first_timeout_reply = app.tick(now_ms=120)
    repeated_timeout_reply = app.tick(now_ms=130)
    state_reply = app.handle_line("STATE?", now_ms=131)

    assert first_timeout_reply == "TIMEOUT,last_seq=8"
    assert repeated_timeout_reply == ""
    assert state_reply.startswith(
        "state=1,state_label=TIMEOUT,last_seq=8,follow_active=0,"
    )
    assert "base_ok=0" in state_reply


def test_assistant_app_returns_err_for_malformed_or_unknown_packets() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    malformed_reply = app.handle_line(
        "follow=1,seq=oops,valid=1,dx=0.10,dy=0.00", now_ms=10
    )
    unknown_reply = app.handle_line("WHATEVER", now_ms=11)
    follow_reply = app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=12)

    assert malformed_reply == "ERR"
    assert unknown_reply == "ERR"
    assert follow_reply == ""


def test_assistant_app_accepts_vel_but_still_rejects_move() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    vel_reply = app.handle_line("VEL 0.1 0.2 0.3", now_ms=10)
    move_reply = app.handle_line("MOVE 0.1 0.2 15", now_ms=11)

    assert vel_reply == "ACK,last_seq=0"
    assert move_reply == "ERR"
