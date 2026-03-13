"""TransportCar Stage 2 安全模式单元测试."""

import builtins
import importlib
import sys
import types
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def _install_transport_stubs() -> None:
    machine = types.ModuleType("machine")

    class Pin:
        OUT = 0
        IN = 1
        PULL_UP_47K = 2

        def __init__(self, *_args, **_kwargs):
            self._value = 1

        def value(self):
            return self._value

        def toggle(self):
            return None

    class UART:
        def __init__(self, *_args, **_kwargs):
            self.messages = []

        def init(self, *_args, **_kwargs):
            return None

        def write(self, text):
            self.messages.append(text)

        def any(self):
            return 0

        def read(self, _size):
            return b""

    setattr(machine, "Pin", Pin)
    setattr(machine, "UART", UART)
    sys.modules["machine"] = machine

    seekfree = types.ModuleType("seekfree")

    class MOTOR_CONTROLLER:
        PWM_C30_DIR_C31 = 1
        PWM_D4_DIR_D5 = 2
        PWM_D6_DIR_D7 = 3

        def __init__(self, *_args, **_kwargs):
            self.last_duty = 0

        def duty(self, value):
            self.last_duty = value

    class IMU660RX:
        def get(self):
            return [0, 0, 0, 0, 0, 0]

    setattr(seekfree, "MOTOR_CONTROLLER", MOTOR_CONTROLLER)
    setattr(seekfree, "IMU660RX", IMU660RX)
    sys.modules["seekfree"] = seekfree

    smartcar = types.ModuleType("smartcar")

    class FakeEncoder:
        def get(self):
            return 0

    def encoder(*_args, **_kwargs):
        return FakeEncoder()

    setattr(smartcar, "encoder", encoder)
    sys.modules["smartcar"] = smartcar


_install_transport_stubs()

import services.transport_car as transport_car_module  # noqa: E402
import services.stage2_smoke as stage2_smoke_module  # noqa: E402


def test_diagnostic_mode_skips_hardware_initializers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_init(*_args, **_kwargs):
        raise AssertionError("hardware init should be skipped")

    monkeypatch.setattr(transport_car_module, "create_imu", fail_init)
    monkeypatch.setattr(transport_car_module, "create_motors", fail_init)
    monkeypatch.setattr(transport_car_module, "create_encoders", fail_init)
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True)

    assert car.diagnostic_mode is True
    assert car.imu is not None
    assert car.chassis_state is not None
    assert car.chassis_state.wheel_states is not None
    assert car.imu.get() == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert sorted(state["name"] for state in car.chassis_state.wheel_states) == [
        "l",
        "m",
        "r",
    ]


def test_diagnostic_mode_keeps_debug_query_tokens_registered() -> None:
    car = transport_car_module.TransportCar(diagnostic_mode=True)

    registered = set(car._router._query_handlers.keys())

    assert {"health", "tick", "imu", "enc", "motor", "vision"} <= registered


def test_diagnostic_mode_wires_vision_transitions_to_breakpoint_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True)

    assert car.vision_coordinator.state_machine._debug_sink == car._emit_vision_debug


def test_stage2_smoke_probe_collects_safe_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    summary = stage2_smoke_module.collect_stage2_summary()

    assert summary["status"] == "ok"
    assert summary["transport_mode"] == "full"
    assert summary["missing_queries"] == []
    assert summary["query_ok"] == 1
    assert summary["step_ok"] == 1
    assert summary["tick_count"] >= 1
    assert set(summary["snapshots"].keys()) == {
        "health",
        "tick",
        "imu",
        "enc",
        "motor",
        "vision",
    }
    assert set(summary["query_outputs"].keys()) == set(stage2_smoke_module.TOKENS)
    assert summary["query_outputs"]["health"].startswith("?health=")


def test_stage2_smoke_probe_clears_stale_runtime_modules() -> None:
    sys.modules["control.wheel"] = types.ModuleType("control.wheel")
    sys.modules["filters.lowpass_filter"] = types.ModuleType("filters.lowpass_filter")

    stage2_smoke_module._clear_modules()

    assert "control.wheel" not in sys.modules
    assert "filters.lowpass_filter" not in sys.modules


def test_stage2_smoke_probe_launcher_stays_tiny() -> None:
    launcher = Path(__file__).resolve().parents[3] / "tools" / "stage2_smoke_probe.py"

    assert launcher.stat().st_size <= 320


def test_stage2_smoke_probe_launcher_collects_gc_before_runtime_import() -> None:
    launcher = Path(__file__).resolve().parents[3] / "tools" / "stage2_smoke_probe.py"
    text = launcher.read_text(encoding="utf-8")

    assert "gc.collect()" in text
    assert text.index("gc.collect()") < text.index("services.stage2_smoke")


def test_stage2_smoke_probe_launcher_avoids_from_import_for_board_compat() -> None:
    launcher = Path(__file__).resolve().parents[3] / "tools" / "stage2_smoke_probe.py"
    text = launcher.read_text(encoding="utf-8")

    assert "from services.stage2_smoke import main" not in text
    assert '"services.stage2_smoke"' in text
    assert "services.stage2_smoke.lite" not in text


def test_stage2_smoke_probe_launcher_imports_package_surface_and_uses_lite_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = Path(__file__).resolve().parents[3] / "tools" / "stage2_smoke_probe.py"
    code = launcher.read_text(encoding="utf-8")
    calls = []

    fake_stage2_smoke = types.ModuleType("services.stage2_smoke")

    def fake_collect_lite_transport_summary():
        calls.append("lite")
        return {"status": "ok"}

    def fail_collect_stage2_summary():
        raise AssertionError("probe should not call collect_stage2_summary()")

    setattr(
        fake_stage2_smoke,
        "_collect_lite_transport_summary",
        fake_collect_lite_transport_summary,
    )
    setattr(fake_stage2_smoke, "collect_stage2_summary", fail_collect_stage2_summary)
    monkeypatch.setitem(sys.modules, "services.stage2_smoke", fake_stage2_smoke)

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "services.stage2_smoke":
            calls.append(name)
            sys.modules[name] = fake_stage2_smoke
            return fake_stage2_smoke
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(builtins, "print", lambda value: calls.append(("print", value)))

    exec(code, {"__name__": "__main__"})

    assert calls == [
        "services.stage2_smoke",
        "lite",
        ("print", {"status": "ok"}),
    ]


def test_stage2_smoke_probe_launcher_clears_stale_stage2_modules_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = Path(__file__).resolve().parents[3] / "tools" / "stage2_smoke_probe.py"
    code = launcher.read_text(encoding="utf-8")
    calls = []

    fake_stage2_smoke = types.ModuleType("services.stage2_smoke")
    setattr(
        fake_stage2_smoke,
        "_collect_lite_transport_summary",
        lambda: {"status": "ok"},
    )
    monkeypatch.setitem(sys.modules, "services.stage2_smoke", fake_stage2_smoke)
    monkeypatch.setitem(
        sys.modules,
        "services.stage2_smoke.lite",
        types.ModuleType("services.stage2_smoke.lite"),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.stage2_smoke.entry",
        types.ModuleType("services.stage2_smoke.entry"),
    )

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "services.stage2_smoke":
            calls.append(
                (
                    "import",
                    name,
                    "services.stage2_smoke" in sys.modules,
                    "services.stage2_smoke.lite" in sys.modules,
                    "services.stage2_smoke.entry" in sys.modules,
                )
            )
            sys.modules[name] = fake_stage2_smoke
            return fake_stage2_smoke
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(builtins, "print", lambda _value: None)

    exec(code, {"__name__": "__main__"})

    assert calls == [
        ("import", "services.stage2_smoke", False, False, False),
    ]


def test_stage2_smoke_probe_launcher_clears_stale_commanding_modules_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launcher = Path(__file__).resolve().parents[3] / "tools" / "stage2_smoke_probe.py"
    code = launcher.read_text(encoding="utf-8")
    calls = []

    fake_stage2_smoke = types.ModuleType("services.stage2_smoke")
    setattr(
        fake_stage2_smoke,
        "_collect_lite_transport_summary",
        lambda: {"status": "ok"},
    )
    monkeypatch.setitem(sys.modules, "services.stage2_smoke", fake_stage2_smoke)
    monkeypatch.setitem(
        sys.modules,
        "services.commanding.handlers",
        types.ModuleType("services.commanding.handlers"),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.commanding.handlers.query_health",
        types.ModuleType("services.commanding.handlers.query_health"),
    )

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "services.stage2_smoke":
            calls.append(
                (
                    "import",
                    name,
                    "services.commanding.handlers" in sys.modules,
                    "services.commanding.handlers.query_health" in sys.modules,
                )
            )
            sys.modules[name] = fake_stage2_smoke
            return fake_stage2_smoke
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(builtins, "print", lambda _value: None)

    exec(code, {"__name__": "__main__"})

    assert calls == [
        ("import", "services.stage2_smoke", False, False),
    ]


def test_stage2_smoke_entry_loads_lite_helper_without_from_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    fake_lite = types.ModuleType("services.stage2_smoke.lite")

    def fake_collect_lite_transport_summary(tokens, check_transport_source_func):
        calls.append(("lite_func", tokens, check_transport_source_func()))
        return {"status": "ok"}

    setattr(
        fake_lite,
        "collect_lite_transport_summary",
        fake_collect_lite_transport_summary,
    )
    monkeypatch.setitem(sys.modules, "services.stage2_smoke.lite", fake_lite)
    monkeypatch.setattr(stage2_smoke_module, "TOKENS", ("health",))
    monkeypatch.setattr(
        stage2_smoke_module, "_check_transport_source", lambda: (True, True)
    )

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "services.stage2_smoke.lite":
            calls.append(("import", tuple(fromlist)))
            if fromlist:
                raise ImportError("board from-import unavailable")
            return sys.modules[name]
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    summary = stage2_smoke_module._collect_lite_transport_summary()

    assert summary == {"status": "ok"}
    assert calls == [
        ("import", ()),
        ("lite_func", ("health",), (True, True)),
    ]


def test_stage2_smoke_runtime_entry_stays_compact_for_device_import() -> None:
    runtime_module = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "services"
        / "stage2_smoke"
        / "entry.py"
    )

    assert runtime_module.stat().st_size <= 10000


def test_stage2_smoke_package_keeps_public_entrypoints() -> None:
    assert hasattr(stage2_smoke_module, "collect_stage2_summary")
    assert hasattr(stage2_smoke_module, "_collect_lite_transport_summary")
    assert hasattr(stage2_smoke_module, "_collect_full_transport_summary")


def test_stage2_smoke_probe_falls_back_to_lite_mode_on_transport_memory_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stage2_smoke_module,
        "_collect_full_transport_summary",
        lambda: (_ for _ in ()).throw(MemoryError("memory")),
    )
    monkeypatch.setattr(
        stage2_smoke_module,
        "_check_transport_source",
        lambda: (True, True),
    )

    summary = stage2_smoke_module.collect_stage2_summary()

    assert summary["status"] == "ok"
    assert summary["transport_mode"] == "lite"
    assert summary["query_ok"] == 1
    assert summary["step_ok"] == 0
    assert summary["tick_count"] == 0


def test_stage2_lite_context_routes_pos_lock_log_queries_through_real_handlers() -> (
    None
):
    import services.commanding.handlers as _commanding_handlers  # noqa: F401 自动发现查询处理器
    from services.commanding.router import router

    ctx = stage2_smoke_module._LiteContext()

    assert router.handle_query("pos", ctx) is True
    assert router.handle_query("lock", ctx) is True
    assert router.handle_query("log", ctx) is True
    assert ctx.uart3.messages == [
        "?pos=0.000,0.000,0.00\r\n",
        "?lock=0\r\n",
        "?log=profile:run,level:info,filter:off,color:0,modules:none\r\n",
    ]


def test_stage2_lite_fallback_probes_pos_lock_log_queries() -> None:
    summary = stage2_smoke_module._collect_lite_transport_summary()

    assert summary["status"] == "ok"
    assert summary["missing_queries"] == []
    assert set(summary["query_outputs"].keys()) == {
        "health",
        "tick",
        "imu",
        "enc",
        "motor",
        "vision",
        "pos",
        "lock",
        "log",
    }
    assert summary["query_outputs"]["pos"] == "?pos=0.000,0.000,0.00"
    assert summary["query_outputs"]["lock"] == "?lock=0"
    assert (
        summary["query_outputs"]["log"]
        == "?log=profile:run,level:info,filter:off,color:0,modules:none"
    )


def test_stage2_lite_summary_uses_query_only_handler_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class LegacyRouter:
        def __init__(self):
            self._query_handlers = {
                name: object() for name in stage2_smoke_module.TOKENS
            }

        def handle_query(self, token, ctx):
            ctx.reply("?%s=ok\r\n" % token)
            return True

    import services.commanding.handlers as handlers_module
    import importlib

    router_module = importlib.import_module("services.commanding.router")

    monkeypatch.setattr(router_module, "router", LegacyRouter())
    monkeypatch.setattr(
        handlers_module,
        "load_query_handlers",
        lambda: calls.append("load_query_handlers"),
    )
    monkeypatch.setattr(
        stage2_smoke_module, "_check_transport_source", lambda: (True, True)
    )

    summary = stage2_smoke_module._collect_lite_transport_summary()

    assert summary["status"] == "ok"
    assert calls == ["load_query_handlers"]


def test_commanding_handlers_package_defers_registration_until_explicit_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in tuple(sys.modules):
        if name == "services.commanding.handlers" or name.startswith(
            "services.commanding.handlers."
        ):
            del sys.modules[name]

    commanding_pkg = sys.modules.get("services.commanding")
    if commanding_pkg is not None and hasattr(commanding_pkg, "handlers"):
        delattr(commanding_pkg, "handlers")

    from services.commanding.router import CommandRouter

    fresh_router = CommandRouter()
    monkeypatch.setitem(
        sys.modules,
        "services.commanding.router",
        types.SimpleNamespace(router=fresh_router, CommandRouter=CommandRouter),
    )

    handlers_module = importlib.import_module("services.commanding.handlers")

    assert fresh_router.registered_query_tokens() == ()
    assert fresh_router._cmd_handlers == {}

    handlers_module.load_query_handlers()

    assert fresh_router.registered_query_tokens() == tuple(
        sorted(stage2_smoke_module.TOKENS)
    )
    assert fresh_router._cmd_handlers == {}


def test_commanding_query_loader_avoids_tuple_startswith_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import services.commanding.handlers as handlers_module

    imported = []

    class StrictName(str):
        def startswith(self, prefix, *args):
            if isinstance(prefix, tuple):
                raise TypeError("can't convert 'tuple' object to str implicitly")
            return super().startswith(prefix, *args)

    previous_query = sys.modules.pop("services.commanding.handlers.query_health", None)
    previous_cmd = sys.modules.pop("services.commanding.handlers.cmd_dx", None)
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in (
            "services.commanding.handlers.query_health",
            "services.commanding.handlers.cmd_dx",
        ):
            imported.append(name)
            module = types.ModuleType(name)
            sys.modules[name] = module
            return module
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(
        handlers_module.os,
        "listdir",
        lambda _path: (
            StrictName("__init__.py"),
            StrictName("cmd_dx.py"),
            StrictName("query_health.py"),
        ),
    )
    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        handlers_module.load_query_handlers()
    finally:
        sys.modules.pop("services.commanding.handlers.query_health", None)
        sys.modules.pop("services.commanding.handlers.cmd_dx", None)
        if previous_query is not None:
            sys.modules["services.commanding.handlers.query_health"] = previous_query
        if previous_cmd is not None:
            sys.modules["services.commanding.handlers.cmd_dx"] = previous_cmd

    assert imported == ["services.commanding.handlers.query_health"]


def test_stage2_lite_summary_accepts_router_without_registered_query_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LegacyRouter:
        def __init__(self):
            self._query_handlers = {
                name: object() for name in stage2_smoke_module.TOKENS
            }

        def handle_query(self, token, ctx):
            ctx.reply("?%s=ok\r\n" % token)
            return True

    monkeypatch.setitem(
        sys.modules,
        "services.commanding.router",
        types.SimpleNamespace(router=LegacyRouter()),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.commanding.handlers",
        types.SimpleNamespace(),
    )
    monkeypatch.setattr(
        stage2_smoke_module, "_check_transport_source", lambda: (True, True)
    )

    summary = stage2_smoke_module._collect_lite_transport_summary()

    assert summary["status"] == "ok"
    assert summary["query_count"] == len(stage2_smoke_module.TOKENS)
    assert summary["missing_queries"] == []


def test_stage2_lite_context_get_query_uart_ignores_legacy_private_field() -> None:
    ctx = stage2_smoke_module._LiteContext()
    setattr(ctx, "reply_uart", ctx.uart6)
    setattr(ctx, "_query_response_uart", ctx.uart3)

    assert ctx.get_query_uart() is ctx.uart6


def test_stage2_lite_context_reply_writes_to_explicit_reply_uart() -> None:
    ctx = stage2_smoke_module._LiteContext()
    setattr(ctx, "reply_uart", ctx.uart6)

    ctx.reply("?health=1\r\n")

    assert ctx.uart6.messages == ["?health=1\r\n"]
    assert ctx.uart3.messages == []


def test_stage2_lite_context_no_longer_exposes_snapshot_wrappers_or_legacy_state() -> (
    None
):
    ctx = stage2_smoke_module._LiteContext()

    assert hasattr(type(ctx), "build_health_snapshot") is False
    assert hasattr(type(ctx), "build_tick_snapshot") is False
    assert hasattr(type(ctx), "build_imu_snapshot") is False
    assert hasattr(type(ctx), "build_encoder_snapshot") is False
    assert hasattr(type(ctx), "build_motor_snapshot") is False
    assert hasattr(type(ctx), "build_vision_snapshot") is False
    assert hasattr(type(ctx), "command_lock") is False
    assert hasattr(type(ctx), "heading_est") is False


def test_stage2_check_transport_source_accepts_explicit_reply_uart_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport_source_ok, query_uart_ok = stage2_smoke_module._check_transport_source()

    assert transport_source_ok is True
    assert query_uart_ok is True


def test_stage2_full_transport_summary_uses_public_transport_entrypoint_and_router_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    query_uarts = []

    class FakeRouterView:
        def registered_query_tokens(self):
            calls.append("registered")
            return stage2_smoke_module.TOKENS

    class FakeCar:
        def __init__(self, diagnostic_mode=False):
            self.diagnostic_mode = diagnostic_mode
            self.pit_flag = False
            self.tick_count = 1
            self.uart3 = stage2_smoke_module._CaptureUart()

        def step(self):
            calls.append("step")
            return True

        def get_diagnostics_facade(self):
            return types.SimpleNamespace(
                build_health_snapshot=lambda: {"alive": 1},
                build_tick_snapshot=lambda: {"count": 1},
                build_imu_snapshot=lambda: {"ok": 1},
                build_encoder_snapshot=lambda: {"m": 0.0},
                build_motor_snapshot=lambda: {"m": 0.0},
                build_vision_snapshot=lambda: {"state": "IDLE"},
            )

        def handle_uart_line(self, line, source="uart6"):
            calls.append((line, source))
            query_uarts.append(self.uart3)
            self.uart3.write("%s=ok\r\n" % line)

    monkeypatch.setattr(stage2_smoke_module, "TOKENS", ("health", "lock"))
    monkeypatch.setitem(
        sys.modules,
        "services.transport_car",
        types.SimpleNamespace(TransportCar=FakeCar),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.commanding.router",
        types.SimpleNamespace(router=FakeRouterView()),
    )

    summary = stage2_smoke_module._collect_full_transport_summary()

    assert summary["status"] == "ok"
    assert summary["query_count"] == 2
    assert summary["missing_queries"] == []
    assert calls[0] == "registered"
    assert calls[1:] == ["step", ("?health", "uart3"), ("?lock", "uart3")]
    assert len(query_uarts) == 2
    assert query_uarts[0] is query_uarts[1]
    assert hasattr(query_uarts[0], "messages")
