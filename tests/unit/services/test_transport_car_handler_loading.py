"""TransportCar 的惰性 handler 装配测试."""

import importlib
import sys
import types

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


def _drop_transport_car_module() -> None:
    for name in tuple(sys.modules):
        if name == "services.car" or name.startswith("services.car."):
            sys.modules.pop(name, None)
    services_pkg = sys.modules.get("services")
    if services_pkg is not None and hasattr(services_pkg, "car"):
        delattr(services_pkg, "car")


def test_import_transport_car_does_not_trigger_full_handler_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()

    calls = []
    fake_handlers = types.ModuleType("services.commanding.handlers")

    def fail_load_all_handlers():
        calls.append("all")
        raise AssertionError("load_all_handlers should not run during import")

    setattr(fake_handlers, "load_all_handlers", fail_load_all_handlers)
    setattr(fake_handlers, "load_query_handlers", lambda: calls.append("query"))
    setattr(fake_handlers, "load_command_handlers", lambda: calls.append("command"))
    monkeypatch.setitem(sys.modules, "services.commanding.handlers", fake_handlers)

    commanding_pkg = importlib.import_module("services.commanding")
    if hasattr(commanding_pkg, "handlers"):
        monkeypatch.delattr(commanding_pkg, "handlers", raising=False)

    importlib.import_module("services.car")

    assert calls == []


def test_import_transport_car_diag_does_not_pull_minimal_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()
    sys.modules.pop("services.runtime.minimal_diagnostics", None)

    importlib.import_module("services.car.diag")

    assert "services.runtime.minimal_diagnostics" not in sys.modules


def test_import_transport_car_does_not_pull_vision_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()

    for name in tuple(sys.modules):
        if name == "vision" or name.startswith("vision."):
            sys.modules.pop(name, None)

    importlib.import_module("services.car")

    assert "services.car.vision" not in sys.modules
    assert "vision.runtime" not in sys.modules
    assert "vision.state_machine" not in sys.modules


def test_transport_car_lazily_loads_query_handlers_before_query_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()

    router_module = importlib.import_module("services.commanding.router")
    fresh_router = router_module.CommandRouter()
    monkeypatch.setattr(router_module, "router", fresh_router)

    calls = []
    fake_handlers = types.ModuleType("services.commanding.handlers")

    def load_all_handlers():
        calls.append("all")

    def load_query_handlers():
        calls.append("query")

        @fresh_router.query("health")
        def handle_query(ctx):
            ctx.reply("?health=ok\r\n")

    setattr(fake_handlers, "load_all_handlers", load_all_handlers)
    setattr(fake_handlers, "load_query_handlers", load_query_handlers)
    setattr(fake_handlers, "load_command_handlers", lambda: calls.append("command"))
    monkeypatch.setitem(sys.modules, "services.commanding.handlers", fake_handlers)

    commanding_pkg = importlib.import_module("services.commanding")
    if hasattr(commanding_pkg, "handlers"):
        monkeypatch.delattr(commanding_pkg, "handlers", raising=False)

    transport_car_module = importlib.import_module("services.car")
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True, vehicle_role="main")

    assert calls == []

    car.handle_uart_line("?health", source="uart3")

    assert calls == ["query"]
    assert car.uart3.messages[-1] == "?health=ok\r\n"


def test_transport_car_lazily_loads_command_handlers_before_command_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()

    router_module = importlib.import_module("services.commanding.router")
    fresh_router = router_module.CommandRouter()
    monkeypatch.setattr(router_module, "router", fresh_router)

    calls = []
    fake_handlers = types.ModuleType("services.commanding.handlers")

    def load_all_handlers():
        calls.append("all")

    def load_command_handlers():
        calls.append("command")

        @fresh_router.command("vx")
        def handle_command(ctx, value):
            ctx.session.last_cmd["vx"] = value

    setattr(fake_handlers, "load_all_handlers", load_all_handlers)
    setattr(fake_handlers, "load_query_handlers", lambda: calls.append("query"))
    setattr(fake_handlers, "load_command_handlers", load_command_handlers)
    monkeypatch.setitem(sys.modules, "services.commanding.handlers", fake_handlers)

    commanding_pkg = importlib.import_module("services.commanding")
    if hasattr(commanding_pkg, "handlers"):
        monkeypatch.delattr(commanding_pkg, "handlers", raising=False)

    transport_car_module = importlib.import_module("services.car")
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True, vehicle_role="main")

    assert calls == []

    car.handle_uart_line("vx=1", source="uart3")

    assert calls == ["command"]
    assert car.command_session.last_cmd["vx"] == 1.0


def test_transport_car_defers_heavy_vision_stack_until_first_coordinator_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()

    for name in tuple(sys.modules):
        if name == "services.runtime.vision_runtime_service":
            sys.modules.pop(name, None)
        if name == "vision" or name.startswith("vision."):
            sys.modules.pop(name, None)

    transport_car_module = importlib.import_module("services.car")
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True, vehicle_role="main")

    coordinator = car._ensure_vision_coordinator()

    assert "services.runtime.vision_runtime_service" in sys.modules
    assert "vision.runtime" in sys.modules
    assert "vision.protocol" not in sys.modules
    assert "vision.state_machine" not in sys.modules
    assert "vision.coordinator" not in sys.modules

    assert coordinator.get_state_name() == "IDLE"
    assert "vision.protocol" in sys.modules
    assert "vision.state_machine" in sys.modules
    assert "vision.coordinator" in sys.modules


def test_transport_car_init_does_not_force_load_vision_mixin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()

    for name in tuple(sys.modules):
        if name == "services.car.vision":
            sys.modules.pop(name, None)

    transport_car_module = importlib.import_module("services.car")
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path: [0.0] * 6,
    )

    def fail_if_called() -> None:
        raise AssertionError("vision mixin should stay deferred during __init__")

    monkeypatch.setattr(
        transport_car_module.core, "_ensure_vision_mixin_loaded", fail_if_called
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True, vehicle_role="main")

    assert car is not None
    assert "services.car.vision" not in sys.modules


def test_transport_car_building_uart_ingress_does_not_pull_vision_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_transport_stubs()
    _drop_transport_car_module()

    for name in tuple(sys.modules):
        if name == "services.runtime.vision_runtime_service":
            sys.modules.pop(name, None)
        if name == "vision" or name.startswith("vision."):
            sys.modules.pop(name, None)

    transport_car_module = importlib.import_module("services.car")
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True, vehicle_role="main")

    ingress = car._ensure_uart_ingress()

    assert ingress is car.uart_ingress
    assert "services.runtime.vision_runtime_service" not in sys.modules
    assert "vision.runtime" not in sys.modules
    assert "vision.protocol" not in sys.modules
    assert "vision.state_machine" not in sys.modules
    assert "vision.coordinator" not in sys.modules
