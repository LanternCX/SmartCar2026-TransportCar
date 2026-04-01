def test_master_main_starts_runtime_when_no_button_is_held(monkeypatch) -> None:
    from master.main import main

    started = {"count": 0}

    def _start_runtime() -> None:
        started["count"] += 1

    monkeypatch.setattr("master.main._read_button_state", lambda pin: False)
    monkeypatch.setattr("master.main._start_runtime", _start_runtime)
    main()

    assert started["count"] == 1


def test_master_read_button_state_propagates_import_error(monkeypatch) -> None:
    import builtins
    import pytest

    from master.main import _read_button_state

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "machine":
            raise ImportError("缺少 machine 模块")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(ImportError, match="缺少 machine 模块"):
        _read_button_state("C8")


def test_master_read_now_ms_propagates_import_error(monkeypatch) -> None:
    import builtins
    import pytest

    from master.main import _read_now_ms

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "time":
            raise ImportError("缺少 time 模块")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(ImportError, match="缺少 time 模块"):
        _read_now_ms()


def test_master_main_rejects_device_root_execution_without_package_path(
    monkeypatch,
) -> None:
    import importlib.util
    from pathlib import Path
    import sys
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    src_root = runtime_root.parent

    for module_name in list(sys.modules):
        if module_name == "master" or module_name.startswith("master."):
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

    with pytest.raises(ModuleNotFoundError, match="master") as exc_info:
        spec.loader.exec_module(module)

    assert exc_info.value.name == "master"


def test_master_main_does_not_swallow_real_package_import_error(monkeypatch) -> None:
    import builtins
    import importlib.util
    from pathlib import Path
    import sys
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    src_root = runtime_root.parent

    for module_name in list(sys.modules):
        if module_name == "master" or module_name.startswith("master."):
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
        if name == "master.app":
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


def test_master_main_does_not_fallback_without_module_not_found_error_name(
    monkeypatch,
) -> None:
    import builtins
    from pathlib import Path
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    source = (runtime_root / "main.py").read_text(encoding="utf-8")

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("master"):
            raise ImportError("No module named 'master'")
        return original_import(name, globals, locals, fromlist, level)

    builtins_dict = dict(vars(builtins))
    builtins_dict.pop("ModuleNotFoundError", None)
    builtins_dict["__import__"] = _import
    module_globals = {
        "__builtins__": builtins_dict,
        "__file__": str(runtime_root / "main.py"),
        "__name__": "__main__",
    }

    with pytest.raises(ImportError, match="No module named 'master'"):
        exec(compile(source, str(runtime_root / "main.py"), "exec"), module_globals)


def test_master_main_does_not_fallback_when_import_error_names_full_module(
    monkeypatch,
) -> None:
    import builtins
    from pathlib import Path
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    source = (runtime_root / "main.py").read_text(encoding="utf-8")

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("master"):
            raise ImportError("No module named 'master.app'", name="master.app")
        return original_import(name, globals, locals, fromlist, level)

    module_globals = {
        "__builtins__": {**dict(vars(builtins)), "__import__": _import},
        "__file__": str(runtime_root / "main.py"),
        "__name__": "__main__",
    }

    with pytest.raises(ImportError, match="No module named 'master.app'") as exc_info:
        exec(compile(source, str(runtime_root / "main.py"), "exec"), module_globals)

    assert exc_info.value.name == "master.app"


def test_master_app_rejects_device_root_import_when_master_package_is_missing(
    monkeypatch,
) -> None:
    import importlib
    from pathlib import Path
    import sys
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    src_root = runtime_root.parent

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

    for module_name in list(sys.modules):
        if module_name == "master.app" or module_name.startswith("master.app."):
            sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError, match="master") as exc_info:
        importlib.import_module("app")

    assert exc_info.value.name == "master"


def test_master_app_does_not_fallback_without_module_not_found_error_name(
    monkeypatch,
) -> None:
    import builtins
    from pathlib import Path
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    source = (runtime_root / "app.py").read_text(encoding="utf-8")

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("master"):
            raise ImportError("No module named 'master'")
        return original_import(name, globals, locals, fromlist, level)

    builtins_dict = dict(vars(builtins))
    builtins_dict.pop("ModuleNotFoundError", None)
    builtins_dict["__import__"] = _import
    module_globals = {
        "__builtins__": builtins_dict,
        "__file__": str(runtime_root / "app.py"),
        "__name__": "app",
    }

    with pytest.raises(ImportError, match="No module named 'master'"):
        exec(compile(source, str(runtime_root / "app.py"), "exec"), module_globals)


def test_master_app_does_not_fallback_when_import_error_names_full_module(
    monkeypatch,
) -> None:
    import builtins
    from pathlib import Path
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    source = (runtime_root / "app.py").read_text(encoding="utf-8")

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("master"):
            raise ImportError(
                "No module named 'master.hw.encoders'",
                name="master.hw.encoders",
            )
        return original_import(name, globals, locals, fromlist, level)

    module_globals = {
        "__builtins__": {**dict(vars(builtins)), "__import__": _import},
        "__file__": str(runtime_root / "app.py"),
        "__name__": "app",
    }

    with pytest.raises(
        ImportError, match="No module named 'master.hw.encoders'"
    ) as exc_info:
        exec(compile(source, str(runtime_root / "app.py"), "exec"), module_globals)

    assert exc_info.value.name == "master.hw.encoders"


def test_master_app_does_not_swallow_real_package_import_error(monkeypatch) -> None:
    import builtins
    import importlib
    from pathlib import Path
    import sys
    import pytest

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    src_root = runtime_root.parent

    monkeypatch.syspath_prepend(str(runtime_root))
    monkeypatch.syspath_prepend(str(src_root))

    for module_name in list(sys.modules):
        if module_name == "master.app" or module_name.startswith("master.app."):
            sys.modules.pop(module_name, None)

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "master.vision.decision":
            raise ModuleNotFoundError("缺少视觉依赖", name="missing_dependency")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(ModuleNotFoundError, match="缺少视觉依赖") as exc_info:
        importlib.import_module("master.app")

    assert exc_info.value.name == "missing_dependency"


def test_master_main_dispatches_pid_identify_when_c8_is_held(monkeypatch) -> None:
    from master.main import main

    called = {"pid": 0}

    def _run_pid_identify() -> None:
        called["pid"] += 1

    monkeypatch.setattr("master.main._read_button_state", lambda pin: pin == "C8")
    monkeypatch.setattr("master.main.run_pid_identify", _run_pid_identify)
    main()

    assert called["pid"] == 1


def test_master_main_dispatches_calibrate_gyro_when_c9_is_held(monkeypatch) -> None:
    from master.main import main

    called = {"calibrate": 0}

    def _run_calibrate_gyro() -> None:
        called["calibrate"] += 1

    monkeypatch.setattr("master.main._read_button_state", lambda pin: pin == "C9")
    monkeypatch.setattr("master.main.run_calibrate_gyro", _run_calibrate_gyro)
    main()

    assert called["calibrate"] == 1


def test_master_start_runtime_builds_loop_and_hands_it_to_driver(monkeypatch) -> None:
    from master.main import _start_runtime

    captured = {"drive_loop": None}
    uart_bundle = {
        "uart3": object(),
        "uart6": object(),
        "uart8": object(),
    }

    class DummyLoop:
        pass

    def _loop_factory(uart_bundle):
        captured["uart_bundle"] = uart_bundle
        return DummyLoop()

    def _drive_loop(loop) -> None:
        captured["drive_loop"] = loop

    monkeypatch.setattr("master.main.MasterRuntimeLoop", _loop_factory)
    monkeypatch.setattr(
        "master.main.build_hw_bundle",
        lambda: {"uart": uart_bundle},
    )
    monkeypatch.setattr("master.main._drive_loop", _drive_loop)
    _start_runtime()

    assert captured["uart_bundle"] is uart_bundle
    assert isinstance(captured["drive_loop"], DummyLoop)


def test_master_start_runtime_keeps_stepping_runtime_loop(monkeypatch) -> None:
    from master.main import _start_runtime

    step_calls = []
    now_values = iter((100, 120, 140))

    class DummyLoop:
        def step(self, now_ms):
            step_calls.append(now_ms)
            if len(step_calls) == 3:
                raise SystemExit(0)

    monkeypatch.setattr(
        "master.main.build_hw_bundle",
        lambda: {"uart": {"uart3": object(), "uart6": object(), "uart8": object()}},
    )
    monkeypatch.setattr(
        "master.main.MasterRuntimeLoop", lambda uart_bundle: DummyLoop()
    )
    monkeypatch.setattr("master.main._read_now_ms", lambda: next(now_values))

    import pytest

    with pytest.raises(SystemExit) as exc_info:
        _start_runtime()

    assert exc_info.value.code == 0
    assert step_calls == [100, 120, 140]


def test_master_app_only_drives_assistant_in_current_stage() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
        }
    )

    assert result["self_target"] == {"kind": "hold"}
    assert result["selected_target"] == "follower"
    assert result["assistant_command"] == "follow=1,seq=1,valid=1,dx=12.000,dy=-6.000"
    assert result["phase"] == "TRACKING"
    assert result["active_uart"] == "uart6"


def test_master_app_enters_center_hold_for_small_error() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=10,valid=1,target=follower,err_x=3,err_y=-4",
        }
    )

    assert result["self_target"] == {"kind": "hold"}
    assert result["selected_target"] == "follower"
    assert result["assistant_command"] == "follow=1,seq=1,valid=0,dx=0.000,dy=0.000"
    assert result["phase"] == "CENTER_HOLD"


def test_master_app_routes_current_selected_target_before_state_machine() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=11,valid=1,target=follower,err_x=9,err_y=0",
        }
    )

    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["assistant_command"] == "follow=1,seq=1,valid=1,dx=9.000,dy=0.000"


def test_master_app_zeroes_command_when_selected_report_is_expired() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"uart": "uart6", "now_ms": 1200})

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "idle"
    assert result["phase"] == "MARKER_MISSING"
    assert result["self_target"] == {"kind": "hold"}


def test_master_app_uses_selected_target_instead_of_last_arrival() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=8,valid=1,target=follower,err_x=1,err_y=1",
            "now_ms": 1010,
        }
    )

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "CENTER_HOLD"
    assert result["active_uart"] == "uart8"


def test_master_app_zeroes_command_when_step_receives_no_new_input() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"now_ms": 1100})

    assert result["assistant_command"] == "follow=1,seq=2,valid=1,dx=12.000,dy=-6.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["self_target"] == {"kind": "hold"}
    assert result["assistant_state"] == {
        "phase": "TRACKING",
        "selected_target": "follower",
        "target_valid": 1,
        "target_fresh": 1,
    }


def test_master_app_keeps_fresh_target_when_same_uart_frame_is_empty() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"uart": "uart6", "now_ms": 1100})

    assert result["assistant_command"] == "follow=1,seq=2,valid=1,dx=12.000,dy=-6.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["self_target"] == {"kind": "hold"}
    assert result["assistant_state"] == {
        "phase": "TRACKING",
        "selected_target": "follower",
        "target_valid": 1,
        "target_fresh": 1,
    }


def test_master_app_zeroes_command_after_selected_target_leaves_freshness_window() -> (
    None
):
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )

    result = app.step({"now_ms": 1200})

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "idle"
    assert result["phase"] == "MARKER_MISSING"


def test_master_app_reuses_explicit_uart_bundle_without_rebuilding_hw(
    monkeypatch,
) -> None:
    from master.app import MasterApp

    build_calls = {"count": 0}
    uart_bundle = {
        "uart3": object(),
        "uart6": object(),
        "uart8": object(),
    }

    def _unexpected_build_hw_bundle():
        build_calls["count"] += 1
        return {
            "uart": uart_bundle,
            "motors": {},
            "encoders": {},
            "imu": object(),
        }

    monkeypatch.setattr("master.app.build_hw_bundle", _unexpected_build_hw_bundle)

    app = MasterApp(uart_bundle=uart_bundle)

    assert build_calls["count"] == 0
    assert app.hw_bundle["uart"] is uart_bundle


def test_master_app_does_not_rejudge_stage_without_new_input(monkeypatch) -> None:
    from master.app import MasterApp

    class FakeStateMachine:
        def __init__(self):
            self.calls = []

        def step(self, **kwargs):
            self.calls.append(dict(kwargs))
            if len(self.calls) == 1:
                return {"phase": "TRACKING", "hold": False}
            return {"phase": "CENTER_HOLD", "hold": True}

    fake_state_machine = FakeStateMachine()
    monkeypatch.setattr(
        "master.app.MarkerStateMachine",
        lambda: fake_state_machine,
    )

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    first = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )
    second = app.step({"now_ms": 1100})

    assert first["phase"] == "TRACKING"
    assert second["phase"] == "TRACKING"
    assert len(fake_state_machine.calls) == 1


def test_master_app_delays_motion_runtime_until_needed(monkeypatch) -> None:
    from master.app import MasterApp

    created = {"count": 0}

    class FakeMotionRuntime:
        def __init__(self):
            created["count"] += 1

        def next_control_seq(self):
            raise AssertionError("hold 路径不应装配运动运行时")

        def apply_self_target(self, target):
            raise AssertionError("hold 路径不应装配运动运行时")

    monkeypatch.setattr("master.app.MotionRuntime", FakeMotionRuntime)

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
        }
    )

    assert created["count"] == 0
    assert result["self_target"] == {"kind": "hold"}


def test_master_app_keeps_center_hold_while_target_is_still_fresh() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=10,valid=1,target=follower,err_x=3,err_y=-4",
            "now_ms": 1000,
        }
    )

    result = app.step({"now_ms": 1100})

    assert result["assistant_command"] == "follow=1,seq=2,valid=0,dx=0.000,dy=0.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "CENTER_HOLD"
    assert result["assistant_state"] == {
        "phase": "CENTER_HOLD",
        "selected_target": "follower",
        "target_valid": 1,
        "target_fresh": 1,
    }


def test_master_app_falls_back_to_configured_uart_when_no_input_arrives() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    result = app.step(None)

    assert result["active_uart"] == "uart6"


def test_master_app_prefers_current_valid_target_over_newer_invalid_report() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=4,valid=1,target=follower,err_x=12,err_y=-6",
        }
    )

    result = app.step(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=5,valid=0,target=follower",
        }
    )

    assert result["assistant_command"] == "follow=1,seq=2,valid=1,dx=12.000,dy=-6.000"
    assert result["selected_target"] == "follower"
    assert result["phase"] == "TRACKING"
    assert result["active_uart"] == "uart6"
