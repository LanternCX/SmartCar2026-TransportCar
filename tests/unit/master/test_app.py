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

    monkeypatch.setattr("master.main._build_capture_ticker", lambda hw_bundle: object())
    monkeypatch.setattr(
        "master.main._build_runtime_heartbeat_led",
        lambda: object(),
        raising=False,
    )
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
    now_values = iter((100, 100, 120, 120, 140))

    class DummyHeartbeatLed:
        def toggle(self) -> None:
            return None

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
    monkeypatch.setattr("master.main._build_capture_ticker", lambda hw_bundle: object())
    monkeypatch.setattr(
        "master.main._build_runtime_heartbeat_led",
        lambda: DummyHeartbeatLed(),
        raising=False,
    )
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
    now_values = iter((100, 100, 100, 103, 105))

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


def test_master_drive_loop_toggles_runtime_heartbeat_slowly(monkeypatch) -> None:
    import pytest

    from master.main import _drive_loop

    step_calls = []
    now_values = iter((100, 100, 350, 350, 650))

    class DummyLoop:
        def __init__(self) -> None:
            self.heartbeat_led = _HeartbeatLed()

        def step(self, now_ms):
            step_calls.append(now_ms)
            if len(step_calls) == 3:
                raise SystemExit(0)

    class _HeartbeatLed:
        def __init__(self) -> None:
            self.toggle_count = 0

        def toggle(self) -> None:
            self.toggle_count += 1

    monkeypatch.setattr("master.main._read_now_ms", lambda: next(now_values))
    monkeypatch.setattr("master.main._sleep_ms", lambda delay_ms: None)

    loop = DummyLoop()

    with pytest.raises(SystemExit) as exc_info:
        _drive_loop(loop)

    assert exc_info.value.code == 0
    assert step_calls == [100, 350, 650]
    assert loop.heartbeat_led.toggle_count == 2


def test_master_drive_loop_reports_lightweight_control_profile_summary(
    monkeypatch,
) -> None:
    import pytest

    from master.main import _drive_loop

    step_calls = []
    debug_events = []
    now_values = iter((100, 105, 610))

    class DummyLoop:
        def step(self, now_ms):
            step_calls.append(now_ms)
            if len(step_calls) == 3:
                raise SystemExit(0)
            return {"self_target": {"kind": "hold"}}

    now_values = iter((100, 105, 200, 205, 610))
    monkeypatch.setattr("master.main._read_now_ms", lambda: next(now_values))
    monkeypatch.setattr("master.main._sleep_ms", lambda delay_ms: None)
    monkeypatch.setattr(
        "master.main._debug_print",
        lambda stage, **payload: debug_events.append((stage, dict(payload))),
    )

    with pytest.raises(SystemExit) as exc_info:
        _drive_loop(DummyLoop())

    assert exc_info.value.code == 0
    assert step_calls == [100, 200, 610]
    assert [stage for stage, _ in debug_events].count("control_period") == 0
    control_profile_events = [
        payload for stage, payload in debug_events if stage == "control_profile"
    ]
    assert len(control_profile_events) == 1
    assert control_profile_events[0]["samples"] == 2
    assert control_profile_events[0]["step_avg_ms"] == 5
    assert control_profile_events[0]["step_max_ms"] == 5
    assert control_profile_events[0]["period_avg_ms"] == 100
    assert control_profile_events[0]["period_max_ms"] == 100


def test_master_build_capture_ticker_registers_encoder_and_imu_devices(
    monkeypatch,
) -> None:
    from master.main import _build_capture_ticker
    import sys
    import types

    captured = {}

    class FakeTicker:
        def capture_list(self, *items):
            captured["items"] = items

        def callback(self, fn):
            captured["callback"] = fn

        def start(self, tick_ms):
            captured["tick_ms"] = tick_ms

    class FakeEncoderPort:
        def __init__(self, device):
            self.device = device

        def ensure_device(self):
            return self.device

    class FakeImuDevice:
        def __init__(self):
            self.get_count = 0

        def get(self):
            self.get_count += 1
            return [0, 0, 0, 0, 0, 0]

    class FakeImuPort:
        def __init__(self, device):
            self.device = device

        def ensure_device(self):
            return self.device

    fake_imu = FakeImuDevice()
    hw_bundle = {
        "encoders": {name: FakeEncoderPort(object()) for name in ("m", "l", "r")},
        "imu": FakeImuPort(fake_imu),
    }

    monkeypatch.setitem(
        sys.modules,
        "smartcar",
        types.SimpleNamespace(ticker=lambda _: FakeTicker()),
    )
    monkeypatch.setattr("master.main._control_tick_ms", lambda: 5)

    ticker_obj = _build_capture_ticker(hw_bundle)

    assert isinstance(ticker_obj, FakeTicker)
    assert len(captured["items"]) == 4
    assert captured["tick_ms"] == 5
    assert fake_imu.get_count == 1


def test_master_app_ignores_removed_follow_payload() -> None:
    from master.app import MasterApp

    app = MasterApp()
    result = app.step(
        {
            "uart": "uart6",
            "line": "v=1,s=9,x=12,y=-6",
            "assistant_feedback": {"state_label": "TRACKING"},
        }
    )

    assert set(result.keys()) == {"self_base_state"}
    assert "assistant_command" not in result
    assert "assistant_state" not in result
    assert "assistant_feedback" not in result
    assert "active_uart" not in result
    assert "reserved_uarts" not in result


def test_master_app_module_no_longer_exports_removed_follow_chain_objects() -> None:
    import master.app as master_app

    assert not hasattr(master_app, "VisionIngress")
    assert not hasattr(master_app, "MarkerStateMachine")
    assert not hasattr(master_app, "decide_from_observation")
    assert not hasattr(master_app, "parse_assistant_state")


def test_master_removed_follow_modules_are_not_importable() -> None:
    import importlib
    import pytest

    for module_name in (
        "master.protocol",
        "master.vision.decision",
        "master.vision.ingress",
        "master.vision.state_machine",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


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


def test_master_app_delays_motion_runtime_until_needed(monkeypatch) -> None:
    from master.app import MasterApp

    created = {"count": 0}

    def _create_runtime_state(hw_bundle=None):
        created["count"] += 1
        return {"hw_bundle": hw_bundle}

    monkeypatch.setattr("master.app.create_runtime_state", _create_runtime_state)

    app = MasterApp()
    result = app.step(
        {
            "uart": "uart6",
            "line": "v=1,s=9,x=12,y=-6",
        }
    )

    assert created["count"] == 0
    assert set(result.keys()) == {"self_base_state"}


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

    import master.motion_runtime as runtime

    app = MasterApp()
    app.motion_state = runtime.create_runtime_state(hw_bundle=None)

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

    app = MasterApp()

    result = app.step({"run_motion": True, "cycle_token": cycle_token})

    assert calls["create"] == 1
    assert calls["run"] == 1
    assert calls["apply"] == [({"hw_bundle": None}, {"kind": "hold"})]
    assert calls["control"] == [({"hw_bundle": None}, None, cycle_token)]
    assert result["self_base_state"]["base_ok"] == 1
