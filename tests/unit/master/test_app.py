from pathlib import Path
import sys

import pytest


RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "src" / "master"
SRC_ROOT = RUNTIME_ROOT.parent
RUNTIME_MODULES = {
    "app",
    "config",
    "decision",
    "main",
    "motion_runtime",
    "protocol",
    "runtime_params",
    "status",
    "vision_ingress",
    "vision_state_machine",
}
RUNTIME_PACKAGES = {"ctrl", "hw", "script", "stability", "vision"}


def _clear_master_runtime_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "master" or module_name.startswith("master."):
            sys.modules.pop(module_name, None)
            continue
        if module_name in RUNTIME_MODULES:
            sys.modules.pop(module_name, None)
            continue
        if module_name.split(".", 1)[0] in RUNTIME_PACKAGES:
            sys.modules.pop(module_name, None)


@pytest.fixture(autouse=True)
def _prepare_master_runtime_imports(monkeypatch):
    _clear_master_runtime_modules()
    monkeypatch.syspath_prepend(str(SRC_ROOT))
    monkeypatch.syspath_prepend(str(RUNTIME_ROOT))
    yield
    _clear_master_runtime_modules()


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
    import master.app as runtime_app

    captured = {"drive_loop": None}
    uart_bundle = {
        "uart3": object(),
        "uart6": object(),
        "uart8": object(),
    }

    class DummyLoop:
        pass

    def _loop_factory(uart_bundle):
        captured["hw_bundle"] = uart_bundle
        return DummyLoop()

    def _drive_loop(loop) -> None:
        captured["drive_loop"] = loop

    monkeypatch.setattr(runtime_app, "MasterRuntimeLoop", _loop_factory)
    monkeypatch.setattr(
        runtime_app,
        "build_hw_bundle",
        lambda: {
            "uart": uart_bundle,
            "motors": {"m": object()},
            "encoders": {"rear_left": object()},
            "imu": object(),
        },
    )
    monkeypatch.setattr("master.main._drive_loop", _drive_loop)
    _start_runtime()

    loop_bundle = captured["hw_bundle"]

    assert loop_bundle is not None
    assert loop_bundle["uart"] is uart_bundle
    assert isinstance(captured["drive_loop"], DummyLoop)


def test_master_start_runtime_keeps_stepping_runtime_loop(monkeypatch) -> None:
    from master.main import _start_runtime
    import master.app as runtime_app

    step_calls = []
    now_values = iter((100, 120, 140))

    class DummyLoop:
        def step(self, now_ms):
            step_calls.append(now_ms)
            if len(step_calls) == 3:
                raise SystemExit(0)

    monkeypatch.setattr(
        runtime_app,
        "build_hw_bundle",
        lambda: {
            "uart": {"uart3": object(), "uart6": object(), "uart8": object()},
            "motors": {"m": object()},
            "encoders": {"rear_left": object()},
            "imu": object(),
        },
    )
    monkeypatch.setattr(runtime_app, "MasterRuntimeLoop", lambda hw_bundle: DummyLoop())
    monkeypatch.setattr("master.main._read_now_ms", lambda: next(now_values))

    import pytest

    with pytest.raises(SystemExit) as exc_info:
        _start_runtime()

    assert exc_info.value.code == 0
    assert step_calls == [100, 120, 140]


def test_master_drive_loop_waits_for_next_5ms_tick(monkeypatch) -> None:
    import pytest

    from master.main import _drive_loop

    step_calls = []
    sleep_calls = []
    now_values = iter((100, 100, 103, 105, 105))

    class DummyLoop:
        def step(self, now_ms):
            step_calls.append(now_ms)
            if len(step_calls) == 2:
                raise SystemExit(0)

    monkeypatch.setattr("master.main._read_now_ms", lambda: next(now_values))
    monkeypatch.setattr(
        "master.main._sleep_ms", lambda delay_ms: sleep_calls.append(delay_ms)
    )

    with pytest.raises(SystemExit) as exc_info:
        _drive_loop(DummyLoop())

    assert exc_info.value.code == 0
    assert step_calls == [100, 105]
    assert sleep_calls == [5, 2]


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


def test_master_runtime_loop_uses_same_full_hw_bundle_owner() -> None:
    from master.app import MasterRuntimeLoop

    hw_bundle = {
        "uart": {"uart3": object(), "uart6": object(), "uart8": object()},
        "motors": {"m": object()},
        "encoders": {"rear_left": object()},
        "imu": object(),
    }

    loop = MasterRuntimeLoop(hw_bundle)

    assert loop.hw_bundle is hw_bundle
    assert loop.app.hw_bundle is hw_bundle


def test_master_app_reuses_explicit_hw_bundle_without_rebuilding_hw(
    monkeypatch,
) -> None:
    from master.app import MasterApp

    build_calls = {"count": 0}
    hw_bundle = {
        "uart": {
            "uart3": object(),
            "uart6": object(),
            "uart8": object(),
        },
        "motors": {},
        "encoders": {},
        "imu": object(),
    }

    def _unexpected_build_hw_bundle():
        build_calls["count"] += 1
        return hw_bundle

    monkeypatch.setattr("master.app.build_hw_bundle", _unexpected_build_hw_bundle)

    app = MasterApp(hw_bundle=hw_bundle)

    assert build_calls["count"] == 0
    assert app.hw_bundle is hw_bundle


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

    def _create_runtime_state(hw_bundle=None):
        created["count"] += 1
        return {"hw_bundle": hw_bundle}

    monkeypatch.setattr("master.app.create_runtime_state", _create_runtime_state)

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


def test_master_app_self_base_state_preserves_runtime_base_ok(monkeypatch) -> None:
    from master.app import MasterApp

    monkeypatch.setattr(
        "master.app.apply_motion_target",
        lambda state, target: dict(target),
    )
    monkeypatch.setattr(
        "master.app.run_base_cycle",
        lambda state, hw_bundle=None, cycle_token=None: {
            "heading_est_deg": 0.0,
            "yaw_rate_deg_s": 0.0,
            "odom": (0.0, 0.0),
            "base_ok": 0,
        },
    )

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.motion_state = object()

    result = app.step(None)

    assert result["self_base_state"]["base_ok"] == 0


def test_master_app_runs_base_cycle_through_process_entry(monkeypatch) -> None:
    import master.app as master_app

    MasterApp = master_app.MasterApp

    calls = {"create": 0, "run": 0, "apply": [], "control": []}
    cycle_token = object()

    def _create_runtime_state(hw_bundle=None):
        calls["create"] += 1
        return {"hw_bundle": hw_bundle}

    def _run_base_cycle(state, hw_bundle=None, cycle_token=None):
        calls["run"] += 1
        assert state == {"hw_bundle": hw_bundle}
        assert cycle_token is not None
        return {
            "heading_est_deg": 12.5,
            "yaw_rate_deg_s": 0.5,
            "odom": (1.0, 2.0),
            "base_ok": 1,
        }

    def _apply_motion_target(state, target):
        calls["apply"].append((state, dict(target)))
        return dict(target)

    def _run_motion_cycle(state, hw_bundle=None, cycle_token=None):
        calls["control"].append((state, hw_bundle, cycle_token))
        return {"target": {"kind": "hold"}}

    monkeypatch.setattr(master_app, "create_runtime_state", _create_runtime_state)
    monkeypatch.setattr(master_app, "run_base_cycle", _run_base_cycle)
    monkeypatch.setattr(
        master_app, "apply_motion_target", _apply_motion_target, raising=False
    )
    monkeypatch.setattr(
        master_app, "run_motion_cycle", _run_motion_cycle, raising=False
    )

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))

    result = app.step({"run_motion": True, "cycle_token": cycle_token})

    assert calls["create"] == 1
    assert calls["run"] == 1
    assert calls["apply"] == [({"hw_bundle": None}, {"kind": "hold"})]
    assert calls["control"] == [({"hw_bundle": None}, None, cycle_token)]
    assert result["self_base_state"]["base_ok"] == 1
