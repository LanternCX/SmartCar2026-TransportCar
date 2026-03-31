def test_assistant_main_starts_runtime_when_no_button_is_held(monkeypatch) -> None:
    from assistant.main import main

    started = {"count": 0}

    def _start_runtime() -> None:
        started["count"] += 1

    monkeypatch.setattr("assistant.main._read_button_state", lambda pin: False)
    monkeypatch.setattr("assistant.main._start_runtime", _start_runtime)
    main()

    assert started["count"] == 1


def _install_device_root_stub_modules(monkeypatch, sys, app_module) -> None:
    import types

    monkeypatch.setitem(sys.modules, "app", app_module)

    script_pkg = types.ModuleType("script")
    monkeypatch.setitem(sys.modules, "script", script_pkg)
    pid_identify = types.ModuleType("script.pid_identify")
    setattr(pid_identify, "main", lambda: None)
    monkeypatch.setitem(sys.modules, "script.pid_identify", pid_identify)
    calibrate_gyro = types.ModuleType("script.calibrate_gyro")
    setattr(calibrate_gyro, "main", lambda: None)
    monkeypatch.setitem(sys.modules, "script.calibrate_gyro", calibrate_gyro)


def test_assistant_main_executes_runtime_loop_when_executed_as_device_root(
    monkeypatch,
) -> None:
    import importlib.util
    from pathlib import Path
    import sys
    import types
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "assistant"
    src_root = runtime_root.parent

    app = types.ModuleType("app")

    class DummyLoop:
        def __init__(self, loop_bundle):
            self.loop_bundle = loop_bundle

        def step(self, now_ms):
            step_calls.append((self.loop_bundle, now_ms))
            raise SystemExit(0)

    step_calls = []
    hw_bundle = {
        "uart": {"uart3": object()},
        "motors": {},
        "encoders": {"rear_left": object()},
        "imu": object(),
    }
    setattr(app, "AssistantRuntimeLoop", DummyLoop)
    setattr(app, "build_hw_bundle", lambda: hw_bundle)
    _install_device_root_stub_modules(monkeypatch, sys, app)

    for module_name in list(sys.modules):
        if module_name == "assistant" or module_name.startswith("assistant."):
            sys.modules.pop(module_name, None)

    monkeypatch.syspath_prepend(str(runtime_root))
    monkeypatch.setattr(
        sys,
        "path",
        [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != src_root.resolve()
        ],
    )
    spec = importlib.util.spec_from_file_location("__main__", runtime_root / "main.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(SystemExit) as exc_info:
        spec.loader.exec_module(module)

    assert exc_info.value.code == 0
    assert len(step_calls) == 1
    assert step_calls[0][0] is hw_bundle
    assert set(step_calls[0][0]) == {"uart", "motors", "encoders", "imu"}
    assert isinstance(step_calls[0][1], int)


def test_assistant_main_does_not_swallow_real_package_import_error(monkeypatch) -> None:
    import builtins
    import importlib.util
    from pathlib import Path
    import sys
    import types
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "assistant"
    src_root = runtime_root.parent

    fallback_app = types.ModuleType("app")
    setattr(fallback_app, "AssistantRuntimeLoop", object)
    setattr(
        fallback_app,
        "build_hw_bundle",
        lambda: {"uart": {"uart3": object()}, "motors": {}},
    )
    _install_device_root_stub_modules(monkeypatch, sys, fallback_app)

    for module_name in list(sys.modules):
        if module_name == "assistant" or module_name.startswith("assistant."):
            sys.modules.pop(module_name, None)

    monkeypatch.syspath_prepend(str(runtime_root))
    monkeypatch.setattr(
        sys,
        "path",
        [
            entry
            for entry in sys.path
            if Path(entry or ".").resolve() != src_root.resolve()
        ],
    )

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "assistant.app":
            raise ModuleNotFoundError("缺少依赖", name="missing_dependency")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    spec = importlib.util.spec_from_file_location("__main__", runtime_root / "main.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(ModuleNotFoundError, match="缺少依赖") as exc_info:
        spec.loader.exec_module(module)

    assert exc_info.value.name == "missing_dependency"


def test_assistant_app_does_not_swallow_real_package_import_error(monkeypatch) -> None:
    import builtins
    import importlib
    from pathlib import Path
    import sys
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "assistant"
    src_root = runtime_root.parent

    monkeypatch.syspath_prepend(str(runtime_root))
    monkeypatch.syspath_prepend(str(src_root))

    for module_name in list(sys.modules):
        if module_name == "assistant.app" or module_name.startswith("assistant.app."):
            sys.modules.pop(module_name, None)

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "assistant.protocol":
            raise ModuleNotFoundError("缺少协议依赖", name="missing_dependency")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(ModuleNotFoundError, match="缺少协议依赖") as exc_info:
        importlib.import_module("assistant.app")

    assert exc_info.value.name == "missing_dependency"


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


def test_assistant_app_handles_ping_and_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    assert app.handle_line("PING", now_ms=0) == "ACK,last_seq=0"
    state = app.handle_line("STATE?", now_ms=1)

    assert state.startswith("state=1,")


def test_assistant_app_maps_auxiliary_entries_to_ack_with_last_seq() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)

    hold_reply = app.handle_line("HOLD", now_ms=11)
    stop_reply = app.handle_line("STOP", now_ms=12)
    reset_reply = app.handle_line("RESET_ODOM", now_ms=13)

    assert hold_reply == "ACK,last_seq=8"
    assert stop_reply == "ACK,last_seq=8"
    assert reset_reply == "ACK,last_seq=8"


def test_assistant_app_keeps_follow_phase_silent_but_reports_timeout() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    follow_reply = app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)
    busy_tick_reply = app.tick(now_ms=50)
    timeout_reply = app.tick(now_ms=120)

    assert follow_reply == ""
    assert busy_tick_reply == ""
    assert timeout_reply == "TIMEOUT,last_seq=8"


def test_assistant_app_reports_timeout_only_once_until_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=10)

    first_timeout_reply = app.tick(now_ms=120)
    repeated_timeout_reply = app.tick(now_ms=130)
    state_reply = app.handle_line("STATE?", now_ms=131)

    assert first_timeout_reply == "TIMEOUT,last_seq=8"
    assert repeated_timeout_reply == ""
    assert state_reply == "state=1,state_label=TIMEOUT,last_seq=8,follow_active=0"


def test_assistant_app_returns_err_for_malformed_or_unknown_packets() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

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
