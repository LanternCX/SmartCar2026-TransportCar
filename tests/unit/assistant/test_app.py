import sys

import pytest


def _clear_assistant_runtime_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "assistant" or module_name.startswith("assistant."):
            sys.modules.pop(module_name, None)


@pytest.fixture(autouse=True)
def _prepare_assistant_runtime_imports(monkeypatch):
    _clear_assistant_runtime_modules()
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "src"))
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
        "encoders": {"m": object(), "l": object(), "r": object()},
        "imu": object(),
    }


def test_flat_uploaded_assistant_app_imports_without_package_context(
    monkeypatch,
) -> None:
    import importlib
    from pathlib import Path

    _clear_assistant_runtime_modules()
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[3] / "src" / "assistant")
    )

    app_module = importlib.import_module("app")

    assert hasattr(app_module, "AssistantRuntimeLoop")


def test_flat_uploaded_assistant_main_imports_without_package_context(
    monkeypatch,
) -> None:
    import importlib
    from pathlib import Path

    _clear_assistant_runtime_modules()
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[3] / "src" / "assistant")
    )

    main_module = importlib.import_module("main")

    assert hasattr(main_module, "main")


def test_flat_uploaded_assistant_start_runtime_runs_full_startup_chain(
    monkeypatch,
) -> None:
    import importlib
    from pathlib import Path

    _clear_assistant_runtime_modules()
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[3] / "src" / "assistant")
    )

    events = []
    hw_bundle = {
        "uart": {"uart3": object()},
        "motors": {},
        "encoders": {},
        "imu": object(),
    }

    class DummyLoop:
        pass

    app_module = importlib.import_module("app")
    main_module = importlib.import_module("main")

    monkeypatch.setattr(
        app_module,
        "build_hw_bundle",
        lambda: hw_bundle,
    )
    monkeypatch.setattr(
        app_module,
        "AssistantRuntimeLoop",
        lambda hw_bundle: events.append(("loop", hw_bundle)) or DummyLoop(),
    )
    monkeypatch.setattr(
        main_module,
        "_build_capture_ticker",
        lambda hw_bundle: events.append(("capture", hw_bundle)) or "capture-ticker",
    )
    monkeypatch.setattr(
        main_module,
        "_build_runtime_heartbeat_led",
        lambda: events.append(("heartbeat", None)) or "heartbeat-led",
    )
    monkeypatch.setattr(
        main_module,
        "_drive_loop",
        lambda loop: events.append(
            (
                "drive",
                getattr(loop, "capture_ticker", None),
                getattr(loop, "heartbeat_led", None),
            )
        ),
    )

    main_module._start_runtime()

    assert events == [
        ("loop", hw_bundle),
        ("capture", hw_bundle),
        ("heartbeat", None),
        ("drive", "capture-ticker", "heartbeat-led"),
    ]


def test_assistant_build_capture_ticker_registers_encoder_and_imu_devices(
    monkeypatch,
) -> None:
    from assistant.main import _build_capture_ticker
    import types

    captured = {}
    events = []

    class FakeTicker:
        def capture_list(self, *items):
            captured["items"] = items
            events.append(("capture_list", items))

        def callback(self, func):
            captured["callback"] = func
            events.append(("callback", func))

        def start(self, tick_ms):
            captured["tick_ms"] = tick_ms
            events.append(("start", tick_ms))

    class FakeEncoderPort:
        def __init__(self, name, device):
            self.name = name
            self.device = device

        def ensure_device(self):
            events.append(("ensure_encoder", self.name, self.device))
            return self.device

    class FakeImuDevice:
        def __init__(self):
            self.get_count = 0

        def get(self):
            self.get_count += 1
            events.append(("imu_get", self.get_count))
            return [0, 0, 0, 0, 0, 0]

    class FakeImuPort:
        def __init__(self, device):
            self.device = device

        def ensure_device(self):
            events.append(("ensure_imu", self.device))
            return self.device

    fake_imu = FakeImuDevice()
    encoder_devices = {name: object() for name in ("m", "l", "r")}
    hw_bundle = {
        "encoders": {
            name: FakeEncoderPort(name, encoder_devices[name])
            for name in ("m", "l", "r")
        },
        "imu": FakeImuPort(fake_imu),
    }

    monkeypatch.setattr("assistant.main._control_tick_ms", lambda: 5)
    monkeypatch.setitem(
        sys.modules,
        "smartcar",
        types.SimpleNamespace(ticker=lambda _channel: FakeTicker()),
    )

    ticker = _build_capture_ticker(hw_bundle)

    assert isinstance(ticker, FakeTicker)
    assert captured["items"] == (
        encoder_devices["m"],
        encoder_devices["l"],
        encoder_devices["r"],
        fake_imu,
    )
    assert captured["tick_ms"] == 5
    assert fake_imu.get_count == 1
    assert len({id(item) for item in captured["items"][:3]}) == 3
    assert events == [
        ("ensure_encoder", "m", encoder_devices["m"]),
        ("ensure_encoder", "l", encoder_devices["l"]),
        ("ensure_encoder", "r", encoder_devices["r"]),
        ("ensure_imu", fake_imu),
        ("imu_get", 1),
        (
            "capture_list",
            (
                encoder_devices["m"],
                encoder_devices["l"],
                encoder_devices["r"],
                fake_imu,
            ),
        ),
        ("callback", captured["callback"]),
        ("start", 5),
    ]


def test_assistant_encoder_port_binds_device_reference_on_first_ensure(
    monkeypatch,
) -> None:
    from assistant.hw.encoders import EncoderPort
    from types import SimpleNamespace

    class FakeEncoderDevice:
        def __init__(self):
            self.get_count = 0

        def get(self):
            self.get_count += 1
            return 0

    fake_device = FakeEncoderDevice()
    monkeypatch.setitem(
        sys.modules,
        "smartcar",
        SimpleNamespace(encoder=lambda *args: fake_device),
    )

    port = EncoderPort("l", "C2", "C3", True)
    port.ensure_device()

    assert getattr(port, "_data_ref", None) == 0
    assert fake_device.get_count == 1


def test_assistant_imu_port_binds_device_reference_on_first_ensure(
    monkeypatch,
) -> None:
    from assistant.hw.imu import ImuPort
    from types import SimpleNamespace

    class FakeImuDevice:
        def __init__(self):
            self.get_count = 0

        def get(self):
            self.get_count += 1
            return (0, 0, 0, 0, 0, 0)

    fake_device = FakeImuDevice()
    monkeypatch.setitem(
        sys.modules,
        "seekfree",
        SimpleNamespace(IMU660RX=lambda: fake_device),
    )

    port = ImuPort()
    port.ensure_device()

    assert getattr(port, "_data_ref", None) == (0, 0, 0, 0, 0, 0)
    assert fake_device.get_count == 1


def test_assistant_main_starts_runtime_when_no_button_is_held(monkeypatch) -> None:
    from assistant.main import main

    started = {"count": 0}
    events = []

    def _start_runtime() -> None:
        started["count"] += 1

    monkeypatch.setattr("assistant.main._read_button_state", lambda pin: False)
    monkeypatch.setattr("assistant.main._start_runtime", _start_runtime)
    monkeypatch.setattr(
        "assistant.main._debug_print",
        lambda stage, **payload: events.append((stage, payload)),
    )
    main()

    assert started["count"] == 1
    assert events == [("main_enter", {}), ("main_branch_runtime", {})]


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


def test_assistant_main_dispatches_calibrate_gyro_when_c9_is_held(monkeypatch) -> None:
    from assistant.main import main

    called = {"calibrate": 0}
    events = []

    def _run_calibrate_gyro() -> None:
        called["calibrate"] += 1

    monkeypatch.setattr("assistant.main._read_button_state", lambda pin: pin == "C9")
    monkeypatch.setattr("assistant.main.run_calibrate_gyro", _run_calibrate_gyro)
    monkeypatch.setattr(
        "assistant.main._debug_print",
        lambda stage, **payload: events.append((stage, payload)),
    )
    main()

    assert called["calibrate"] == 1
    assert events == [("main_enter", {}), ("main_branch_calibrate_gyro", {})]


def test_assistant_main_dispatches_pid_identify_when_c8_is_held(monkeypatch) -> None:
    from assistant.main import main

    called = {"pid": 0}
    events = []

    def _run_pid_identify() -> None:
        called["pid"] += 1

    monkeypatch.setattr("assistant.main._read_button_state", lambda pin: pin == "C8")
    monkeypatch.setattr("assistant.main.run_pid_identify", _run_pid_identify)
    monkeypatch.setattr(
        "assistant.main._debug_print",
        lambda stage, **payload: events.append((stage, payload)),
    )
    main()

    assert called["pid"] == 1
    assert events == [("main_enter", {}), ("main_branch_pid_identify", {})]


def test_assistant_read_button_state_reports_pin_and_pressed_state(monkeypatch) -> None:
    from assistant.main import _read_button_state
    from types import SimpleNamespace

    events = []

    class FakePin:
        IN = object()
        PULL_UP = object()

        def __init__(self, name, mode, pull):
            self.name = name

        def value(self):
            return 0

    monkeypatch.setitem(sys.modules, "machine", SimpleNamespace(Pin=FakePin))
    monkeypatch.setattr(
        "assistant.main._debug_print",
        lambda stage, **payload: events.append((stage, payload)),
    )

    pressed = _read_button_state("C8")

    assert pressed is True
    assert events == [("button_state", {"pin": "C8", "pressed": 1})]


def test_assistant_start_runtime_builds_loop_and_hands_it_to_driver(
    monkeypatch,
) -> None:
    from assistant.main import _start_runtime
    import assistant.app as runtime_app

    captured = {"drive_loop": None, "events": []}
    uart3 = object()
    motors = {"m": object()}
    hw_bundle = {
        "uart": {"uart3": uart3},
        "motors": motors,
        "encoders": {"m": object(), "l": object(), "r": object()},
        "imu": object(),
    }

    class DummyLoop:
        pass

    def _loop_factory(loop_bundle):
        captured["loop_bundle"] = loop_bundle
        captured["events"].append(("loop_factory", loop_bundle))
        return DummyLoop()

    def _drive_loop(loop) -> None:
        captured["events"].append(
            (
                "drive_loop",
                getattr(loop, "capture_ticker", None),
                getattr(loop, "heartbeat_led", None),
            )
        )
        captured["drive_loop"] = loop

    monkeypatch.setattr(
        "assistant.main._build_capture_ticker",
        lambda bundle: (
            captured["events"].append(("build_capture", bundle)) or ("capture", bundle)
        ),
    )
    monkeypatch.setattr(
        "assistant.main._build_runtime_heartbeat_led",
        lambda: captured["events"].append(("build_heartbeat", None)) or "heartbeat",
    )
    monkeypatch.setattr(
        "assistant.main._debug_print",
        lambda stage, **payload: captured["events"].append(("debug", stage, payload)),
    )

    monkeypatch.setattr(runtime_app, "AssistantRuntimeLoop", _loop_factory)
    monkeypatch.setattr(runtime_app, "build_hw_bundle", lambda: hw_bundle)
    monkeypatch.setattr("assistant.main._drive_loop", _drive_loop)
    _start_runtime()

    loop_bundle = captured["loop_bundle"]

    assert loop_bundle is not None
    assert loop_bundle is hw_bundle
    assert isinstance(captured["drive_loop"], DummyLoop)
    assert getattr(captured["drive_loop"], "capture_ticker") == ("capture", hw_bundle)
    assert getattr(captured["drive_loop"], "heartbeat_led") == "heartbeat"
    assert captured["events"] == [
        ("debug", "start_runtime_enter", {}),
        (
            "debug",
            "start_runtime_hw_ready",
            {"keys": ("encoders", "imu", "motors", "uart")},
        ),
        ("loop_factory", hw_bundle),
        ("build_capture", hw_bundle),
        ("build_heartbeat", None),
        ("debug", "start_runtime_loop_ready", {}),
        ("drive_loop", ("capture", hw_bundle), "heartbeat"),
    ]


def test_assistant_build_capture_ticker_reports_ready_after_start(monkeypatch) -> None:
    from assistant.main import _build_capture_ticker
    import types

    events = []

    class FakeTicker:
        def capture_list(self, *items):
            events.append(("capture_list", items))

        def callback(self, func):
            events.append(("callback", func))

        def start(self, tick_ms):
            events.append(("start", tick_ms))

    class FakeEncoderPort:
        def __init__(self, device):
            self.device = device

        def ensure_device(self):
            return self.device

    class FakeImuDevice:
        def get(self):
            events.append(("imu_get", None))
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

    monkeypatch.setattr("assistant.main._control_tick_ms", lambda: 5)
    monkeypatch.setitem(
        sys.modules,
        "smartcar",
        types.SimpleNamespace(ticker=lambda _channel: FakeTicker()),
    )
    monkeypatch.setattr(
        "assistant.main._debug_print",
        lambda stage, **payload: events.append(("debug", stage, payload)),
    )

    _build_capture_ticker(hw_bundle)

    assert events[-1] == ("debug", "capture_ticker_ready", {"count": 4})


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


def test_assistant_drive_loop_toggles_runtime_heartbeat_slowly(monkeypatch) -> None:
    import pytest

    from assistant.main import _drive_loop

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

    monkeypatch.setattr("assistant.main._read_now_ms", lambda: next(now_values))
    monkeypatch.setattr("assistant.main._sleep_ms", lambda delay_ms: None)

    loop = DummyLoop()

    with pytest.raises(SystemExit) as exc_info:
        _drive_loop(loop)

    assert exc_info.value.code == 0
    assert step_calls == [100, 350, 650]
    assert loop.heartbeat_led.toggle_count == 2


def test_assistant_app_handles_ping_and_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    assert app.handle_line("PING", now_ms=0) == "ACK,last_seq=0"
    state = app.handle_line("STATE?", now_ms=1)

    assert state.startswith("state=1,")


def _assert_follow_ack(reply, seq, valid) -> None:
    parts = str(reply).split(",")

    assert parts[0] == "K"
    assert int(parts[1]) == seq
    assert int(parts[2]) == valid


def test_assistant_app_maps_auxiliary_entries_to_ack_with_last_seq() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    app.handle_line("f=1,s=8,v=1,x=0.10,y=0.00", now_ms=10)

    hold_reply = app.handle_line("HOLD", now_ms=11)
    stop_reply = app.handle_line("STOP", now_ms=12)
    reset_reply = app.handle_line("RESET_ODOM", now_ms=13)

    assert hold_reply == "ACK,last_seq=8"
    assert stop_reply == "ACK,last_seq=8"
    assert reset_reply == "ACK,last_seq=8"


def test_assistant_app_replies_to_follow_during_debug_and_keeps_timeout_silent() -> (
    None
):
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    follow_reply = app.handle_line("f=1,s=8,v=1,x=0.10,y=0.00", now_ms=10)
    busy_tick_reply = app.tick(now_ms=50)
    timeout_reply = app.tick(now_ms=120)

    _assert_follow_ack(follow_reply, 8, 1)
    assert busy_tick_reply == ""
    assert timeout_reply == ""


def test_assistant_app_exposes_timeout_only_via_state_query() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    app.handle_line("f=1,s=8,v=1,x=0.10,y=0.00", now_ms=10)

    first_timeout_reply = app.tick(now_ms=120)
    repeated_timeout_reply = app.tick(now_ms=130)
    state_reply = app.handle_line("STATE?", now_ms=131)

    assert first_timeout_reply == ""
    assert repeated_timeout_reply == ""
    assert state_reply.startswith(
        "state=1,state_label=TIMEOUT,last_seq=8,follow_active=0,"
    )
    assert "base_ok=0" in state_reply


def test_assistant_app_returns_err_for_malformed_or_unknown_packets() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    malformed_reply = app.handle_line("f=1,s=oops,v=1,x=0.10,y=0.00", now_ms=10)
    unknown_reply = app.handle_line("WHATEVER", now_ms=11)
    follow_reply = app.handle_line("f=1,s=8,v=1,x=0.10,y=0.00", now_ms=12)

    assert malformed_reply.startswith("ERR,reason=invalid_literal_for_int,")
    assert malformed_reply.endswith("raw=f=1,s=oops,v=1,x=0.10,y=0.00")
    assert unknown_reply.startswith("ERR,reason=unsupported_command,")
    assert unknown_reply.endswith("raw=WHATEVER")
    _assert_follow_ack(follow_reply, 8, 1)


def test_assistant_app_returns_err_for_follow_packet_missing_valid_field() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100, hw_bundle=_build_fake_hw_bundle())

    reply = app.handle_line("f=1,s=8,x=0.10,y=0.00", now_ms=12)

    assert reply.startswith("ERR,reason=missing_required_field,")
    assert reply.endswith("raw=f=1,s=8,x=0.10,y=0.00")


def test_assistant_app_accepts_vel_but_still_rejects_move() -> None:
    from assistant.app import AssistantApp

    app = AssistantApp(timeout_ms=100)

    vel_reply = app.handle_line("VEL 0.1 0.2 0.3", now_ms=10)
    move_reply = app.handle_line("MOVE 0.1 0.2 15", now_ms=11)

    assert vel_reply == "ACK,last_seq=0"
    assert move_reply == "ERR,reason=unsupported_command,raw=MOVE 0.1 0.2 15"


def test_assistant_app_routes_through_procedural_runtime_entries(monkeypatch) -> None:
    import assistant.app as runtime_app

    hw_bundle = _build_fake_hw_bundle()
    runtime_state = type(
        "RuntimeState",
        (),
        {
            "last_seq": 0,
            "timeout": False,
            "hw_bundle": hw_bundle,
        },
    )()
    captured = {"created": [], "commands": [], "cycles": []}

    def _create_runtime_state(timeout_ms=None, hw_bundle=None):
        captured["created"].append((timeout_ms, hw_bundle))
        return runtime_state

    def _apply_runtime_command(state, command, now_ms, cycle_token=None):
        captured["commands"].append((state, command.kind, now_ms, cycle_token))
        return "ACK"

    def _run_base_cycle(state, now_ms, cycle_token=None, hw_bundle=None):
        captured["cycles"].append((state, now_ms, cycle_token, hw_bundle))
        return "ACK"

    monkeypatch.setattr(runtime_app, "create_runtime_state", _create_runtime_state)
    monkeypatch.setattr(runtime_app, "apply_runtime_command", _apply_runtime_command)
    monkeypatch.setattr(runtime_app, "run_base_cycle", _run_base_cycle)

    app = runtime_app.AssistantApp(timeout_ms=100, hw_bundle=hw_bundle)

    reply = app.handle_line("PING", now_ms=10, cycle_token="cmd-cycle")
    tick_reply = app.tick(now_ms=15, cycle_token="tick-cycle")

    assert captured["created"] == [(100, hw_bundle)]
    assert reply == "ACK,last_seq=0"
    assert tick_reply == ""
    assert captured["commands"] == [(runtime_state, "ping", 10, "cmd-cycle")]
    assert captured["cycles"] == [(runtime_state, 15, "tick-cycle", hw_bundle)]


def test_assistant_runtime_loop_rejects_legacy_runtime_owner_backtrack() -> None:
    import pytest

    from assistant.app import AssistantRuntimeLoop

    class DummyApp:
        def __init__(self, hw_bundle):
            self.runtime = type(
                "LegacyRuntime",
                (),
                {"core": type("LegacyCore", (), {"hw_bundle": hw_bundle})()},
            )()

        def handle_line(self, line, now_ms, cycle_token=None):
            return ""

        def tick(self, now_ms, cycle_token=None):
            return ""

    hw_bundle = _build_fake_hw_bundle()

    with pytest.raises(ValueError, match="唯一 hw_bundle owner"):
        AssistantRuntimeLoop(hw_bundle, app=DummyApp(hw_bundle=hw_bundle))
