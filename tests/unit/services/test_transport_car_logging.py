"""TransportCar 日志接线单元测试."""

from pathlib import Path
import sys
import types
from typing import Any, cast

import pytest

from diagnostics.sink import UartSink
from diagnostics.manager import LogManager
from services.commanding.context import TransportCommandContext
from services.commanding.session import CommandSession


pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]


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

import services.car as transport_car_module  # noqa: E402
from services.runtime.diagnostics_facade import DiagnosticsFacade  # noqa: E402


class FakeUART:
    """测试串口假对象."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def write(self, text: str) -> None:
        self.messages.append(text)

    def any(self) -> int:
        return 0

    def read(self, _size: int) -> bytes:
        return b""


class FakeRouter:
    """测试路由器假对象."""

    def __init__(self) -> None:
        self.routed: list[tuple[str, object]] = []

    def route(self, line: str, ctx: object) -> None:
        self.routed.append((line, ctx))


def _build_test_logger_manager(uart: object) -> LogManager:
    return LogManager(sinks=[cast(Any, UartSink(cast(Any, uart)))])


def _read_repo_text(relative_path: str) -> str:
    """读取仓库内文本文件内容."""
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_transport_car_staged_init_builds_core_runtime_before_optional_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_order = []

    def fake_init_core_runtime(self) -> None:
        call_order.append("core")
        self.uart3 = FakeUART()
        self.uart6 = FakeUART()
        self.logger_manager = object()
        self._command_session = CommandSession()
        self.chassis_state = object()

    def fake_init_optional_features(self) -> None:
        call_order.append("optional")
        assert self.uart3 is not None
        assert self.logger_manager is not None
        assert self.command_session is not None
        assert self.chassis_state is not None
        self.vision_runtime = object()

    monkeypatch.setattr(
        transport_car_module.TransportCar,
        "_init_core_runtime",
        fake_init_core_runtime,
        raising=False,
    )
    monkeypatch.setattr(
        transport_car_module.TransportCar,
        "_init_optional_features",
        fake_init_optional_features,
        raising=False,
    )

    car = transport_car_module.TransportCar(vehicle_role="main")

    assert call_order == ["core", "optional"]
    assert car.vision_runtime is not None


def test_transport_car_boot_logs_go_through_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uart3 = FakeUART()
    uart6 = FakeUART()
    monkeypatch.setattr(transport_car_module, "create_uart3", lambda: uart3)
    monkeypatch.setattr(transport_car_module, "create_uart6", lambda: uart6)
    monkeypatch.setattr(
        transport_car_module,
        "create_imu",
        lambda: types.SimpleNamespace(get=lambda: [0.0] * 6),
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_motors",
        lambda: {
            name: types.SimpleNamespace(duty=lambda _value: None)
            for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_encoders",
        lambda: {
            name: types.SimpleNamespace(get=lambda: 0.0) for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    transport_car_module.TransportCar(vehicle_role="main")

    assert any(line.startswith("I [system.boot") for line in uart3.messages)
    assert any("System Starting" in line for line in uart3.messages)


def test_transport_car_boot_does_not_emit_temporary_memory_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uart3 = FakeUART()
    uart6 = FakeUART()
    monkeypatch.setattr(transport_car_module, "create_uart3", lambda: uart3)
    monkeypatch.setattr(transport_car_module, "create_uart6", lambda: uart6)
    monkeypatch.setattr(
        transport_car_module,
        "create_imu",
        lambda: types.SimpleNamespace(get=lambda: [0.0] * 6),
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_motors",
        lambda: {
            name: types.SimpleNamespace(duty=lambda _value: None)
            for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_encoders",
        lambda: {
            name: types.SimpleNamespace(get=lambda: 0.0) for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    transport_car_module.TransportCar(vehicle_role="main")

    mem_lines = [line for line in uart3.messages if line.startswith("MEM ")]

    assert mem_lines == []


def test_transport_car_skips_gyro_offset_info_log_during_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uart3 = FakeUART()
    uart6 = FakeUART()
    monkeypatch.setattr(transport_car_module, "create_uart3", lambda: uart3)
    monkeypatch.setattr(transport_car_module, "create_uart6", lambda: uart6)
    monkeypatch.setattr(
        transport_car_module,
        "create_imu",
        lambda: types.SimpleNamespace(get=lambda: [0.0] * 6),
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_motors",
        lambda: {
            name: types.SimpleNamespace(duty=lambda _value: None)
            for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(
        transport_car_module,
        "create_encoders",
        lambda: {
            name: types.SimpleNamespace(get=lambda: 0.0) for name in ("m", "l", "r")
        },
    )
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})

    received = {"logger": object()}

    def fake_load_gyro_offsets(_path: str, logger=None):
        received["logger"] = logger
        return [0.0] * 6

    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        fake_load_gyro_offsets,
    )

    transport_car_module.TransportCar(vehicle_role="main")

    assert received["logger"] is None


def test_transport_car_error_path_uses_raw_uart_fallback() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()
    car.log_health = _build_test_logger_manager(car.uart3).get_logger("system.health")
    car.last_exception_text = "none"
    car.error_count = 0
    car.last_error_stage = None
    car._last_error_log_text = None

    car._emit_error_log("imu init failed")

    assert car.last_exception_text == "imu init failed"
    assert car.error_count == 1
    assert car.last_error_stage == "runtime"
    assert car.uart3.messages == ["ERRRAW imu init failed\r\n"]


def test_transport_car_repeated_error_log_updates_state_without_log_storm() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()
    car.logger_manager = _build_test_logger_manager(car.uart3)
    car.log_health = car.logger_manager.get_logger("system.health")
    car.last_exception_text = "none"
    car.error_count = 0
    car.last_error_stage = None
    car._last_error_log_text = None

    car._emit_error_log("uart ingress failed")
    first_count = len(car.uart3.messages)
    car._emit_error_log("uart ingress failed")

    assert car.last_exception_text == "uart ingress failed"
    assert car.error_count == 2
    assert car.last_error_stage == "runtime"
    assert len(car.uart3.messages) == first_count


def test_transport_car_error_path_falls_back_to_raw_uart_when_logger_ooms() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()

    class OomLogger:
        def error(self, _message: str) -> None:
            raise MemoryError("format oom")

    car.log_health = OomLogger()
    car.last_exception_text = "none"
    car.error_count = 0
    car.last_error_stage = None
    car._last_error_log_text = None

    car._emit_error_log("uart ingress failed")

    assert car.last_exception_text == "uart ingress failed"
    assert car.error_count == 1
    assert car.last_error_stage == "runtime"
    assert car.uart3.messages == ["ERRRAW uart ingress failed\r\n"]


def test_transport_car_error_path_does_not_call_structured_logger() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()

    class FailingLogger:
        def error(self, _message: str) -> None:
            raise AssertionError("structured logger should not run")

    car.log_health = FailingLogger()
    car.last_exception_text = "none"
    car.error_count = 0
    car.last_error_stage = None
    car._last_error_log_text = None

    car._emit_error_log("runtime failed")

    assert car.uart3.messages == ["ERRRAW runtime failed\r\n"]


def test_transport_car_uart3_command_echo_uses_command_logger() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()
    car.logger_manager = _build_test_logger_manager(car.uart3)
    car.log_command = car.logger_manager.get_logger("services.command")
    car._router = FakeRouter()
    car.vision_coordinator = types.SimpleNamespace(
        consume_uart_line=lambda *_args, **_kwargs: False
    )
    car.apply_command = lambda line, source="uart3": car._router.route(line, car)
    car._now_ms = lambda: 1000

    car._handle_uart_line("vx=1", source="uart3")

    assert car.uart3.messages[-1].startswith("I [services.comm+]")
    assert "RCV: vx=1" in car.uart3.messages[-1]


def test_protocol_and_hil_docs_use_physical_camera_ids() -> None:
    protocol_text = _read_repo_text(
        ".agents/skills/using-rules/references/openart-protocol.md"
    )
    strategy_text = _read_repo_text("docs/developer/strategy.md")
    hil_text = _read_repo_text("tests/hil/2026-03-dual-camera-polling.md")

    assert "?frame=cam_a" in protocol_text
    assert "?frame=cam_b" in protocol_text
    assert "?frame=obstacle" not in protocol_text
    assert "?frame=cargo" not in protocol_text
    assert "`camera_id` 只表示物理相机身份" in strategy_text
    assert "`category` 只表示检测类别, 可在不同物理相机上重复出现" in strategy_text
    assert "?frame=cam_a" in hil_text
    assert "?frame=cam_b" in hil_text
    assert "?frame=obstacle" not in hil_text
    assert "?frame=cargo" not in hil_text


def test_transport_car_vision_frame_boundary_logs_without_poll_noise() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()
    car.uart6 = FakeUART()
    car.logger_manager = _build_test_logger_manager(car.uart3)
    car.log_vision = car.logger_manager.get_logger("vision.state")
    car.log_command = car.logger_manager.get_logger("services.command")
    car.log_health = car.logger_manager.get_logger("system.health")
    car.role_profile = types.SimpleNamespace(
        vehicle_role="main",
        vision_processing_enabled=True,
        dual_camera_polling_enabled=True,
        single_task_state_machine_enabled=True,
    )
    car._router = FakeRouter()
    car.apply_command = lambda line, source="uart6": None
    car._now_ms = lambda: 1000
    car.now_ms = car._now_ms
    car.vision_coordinator = transport_car_module.VisionCoordinator(
        protocol=transport_car_module.VisionProtocol(timeout_ms=200),
        state_machine=types.SimpleNamespace(
            step=lambda _inputs: None, reset=lambda: None
        ),
    )
    car.uart_ingress = transport_car_module.UartIngressService(
        router=car._router,
        ensure_query_handlers=lambda: None,
        vision_coordinator=car.vision_coordinator,
        build_context=lambda source: {"source": source},
        apply_command=car.apply_command,
        command_log=lambda line: None,
        emit_error=car._emit_error_log,
        now_ms=car._now_ms,
    )

    car._poll_vision_cameras(poll_budget=1)
    car._handle_uart_line(
        "camera_id=cam_b,frame_id=7,category=obstacle,left=10,top=20,right=50,bottom=80",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_b,frame_id=7,frame_end=1", source="uart6")

    assert not any("POLL camera=cam_b" in line for line in car.uart3.messages)
    assert not any(
        "FRAME camera=cam_b frame=7 end detections=1" in line
        for line in car.uart3.messages
    )


def test_transport_car_vision_frame_boundary_logs_in_debug_level() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.uart3 = FakeUART()
    car.logger_manager = _build_test_logger_manager(car.uart3)
    car.logger_manager.set_level_name("DEBUG")
    car.log_vision = car.logger_manager.get_logger("vision.state")

    car._log_vision_frame_boundary("cam_b", "7", 1)

    assert any(
        "FRAME camera=cam_b frame=7 end detections=1" in line
        for line in car.uart3.messages
    )


def test_transport_car_vision_debug_does_not_rebuild_logger_sink_every_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.log_vision = object()
    sink_builds = []
    received_events = []

    def fake_build_logger_debug_sink(logger):
        sink_builds.append(logger)

        def sink(event):
            received_events.append(event)

        return sink

    monkeypatch.setattr(
        transport_car_module,
        "build_logger_debug_sink",
        fake_build_logger_debug_sink,
    )
    event = object()

    car._emit_vision_debug(event)
    car._emit_vision_debug(event)

    assert sink_builds == [car.log_vision]
    assert received_events == [event, event]


def test_transport_car_records_logger_oom_into_runtime_health_fields() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    car.oom_count = 0
    car.last_oom_stage = None

    car._record_oom("format")
    car._record_oom("sink")

    assert car.oom_count == 2
    assert car.last_oom_stage == "sink"


def test_diagnostics_facade_reuses_cached_vision_snapshot_in_health_query() -> None:
    runtime = types.SimpleNamespace(
        boot_time_ms=1000,
        now_ms=lambda: 2500,
        command_session=CommandSession(),
        last_exception_text="none",
        tick_count=0,
        last_loop_dt_us=0,
        max_loop_dt_us=0,
        loop_dt_total_us=0,
        loop_overrun_count=0,
        oom_count=0,
        last_oom_stage=None,
        logger_manager=types.SimpleNamespace(
            filter_modules=[],
            profile_name="DEFAULT",
            level_name="INFO",
            filter_mode="allow",
            color_enabled=False,
        ),
        vision_runtime=types.SimpleNamespace(
            latest_observation=None,
            selected_input=None,
            resolved_target=None,
        ),
        vision_coordinator=types.SimpleNamespace(get_state_name=lambda: "ALIGN_DX"),
        chassis_state=types.SimpleNamespace(
            heading_est=0.0,
            imu_data=[1],
            wheel_states=[],
            target_speeds={},
            odometry=types.SimpleNamespace(x=0.0, y=0.0),
        ),
    )
    runtime.command_session.command_lock = False
    runtime.command_session.rear_only_mode = False
    facade = DiagnosticsFacade(runtime)
    calls = []
    real_build_vision_snapshot = facade.build_vision_snapshot

    def tracked_build_vision_snapshot():
        calls.append("vision")
        return real_build_vision_snapshot()

    facade.build_vision_snapshot = tracked_build_vision_snapshot

    health_snapshot = facade.build_health_snapshot()

    assert health_snapshot["vision_state"] == "ALIGN_DX"
    assert calls == []


def test_transport_car_get_query_uart_defaults_to_uart6() -> None:
    car = cast(
        Any,
        transport_car_module.TransportCar.__new__(transport_car_module.TransportCar),
    )
    uart6 = FakeUART()
    car.uart6 = uart6

    assert car.get_query_uart() is uart6


def test_transport_command_context_finalize_route_uses_runtime_public_methods() -> None:
    inverse_calls = []
    runtime = types.SimpleNamespace(
        command_session=CommandSession(),
        uart3=FakeUART(),
        logger_manager=LogManager(),
        chassis_state=types.SimpleNamespace(
            odometry=types.SimpleNamespace(x=1.0, y=2.0),
            heading_est=15.0,
            heading_target=30.0,
        ),
        now_ms=lambda: 1234,
        inverse_kinematics=lambda vx, vy, omega: inverse_calls.append((vx, vy, omega)),
        _now_ms=lambda: (_ for _ in ()).throw(
            AssertionError("should use public now_ms")
        ),
        _inverse_kinematics=lambda *_args: (_ for _ in ()).throw(
            AssertionError("should use public inverse_kinematics")
        ),
    )
    runtime.command_session.last_cmd = {"vx": 1.0, "vy": -2.0, "omega": 3.0}

    ctx = TransportCommandContext(runtime, reply_uart=FakeUART(), source="uart6")

    ctx.finalize_route(set())

    assert inverse_calls == [(1.0, -2.0, 3.0)]


def test_transport_command_context_finalize_route_requires_public_runtime_methods() -> (
    None
):
    runtime = types.SimpleNamespace(
        command_session=CommandSession(),
        uart3=FakeUART(),
        logger_manager=LogManager(),
        chassis_state=types.SimpleNamespace(
            odometry=types.SimpleNamespace(x=1.0, y=2.0),
            heading_est=15.0,
            heading_target=30.0,
        ),
        _now_ms=lambda: 1234,
        _inverse_kinematics=lambda vx, vy, omega: (vx, vy, omega),
    )
    runtime.command_session.last_cmd = {"vx": 1.0, "vy": -2.0, "omega": 3.0}

    ctx = TransportCommandContext(runtime, reply_uart=FakeUART(), source="uart6")

    with pytest.raises(AttributeError):
        ctx.finalize_route(set())


def test_transport_command_context_reset_runtime_clears_vision_via_public_coordinator() -> (
    None
):
    clear_calls = []

    class FakeYawPid:
        def reset(self) -> None:
            return None

    runtime = types.SimpleNamespace(
        command_session=CommandSession(),
        uart3=FakeUART(),
        logger_manager=LogManager(),
        chassis_state=types.SimpleNamespace(
            odometry=types.SimpleNamespace(reset=lambda: None),
            heading_est=12.0,
            heading_target=18.0,
            yaw_pid=FakeYawPid(),
            yaw_integral=3.0,
            q_est=types.SimpleNamespace(w=0.0, x=1.0, y=2.0, z=3.0),
            last_yaw_rad=4.0,
            gyro_lpf=types.SimpleNamespace(reset=lambda _value: None),
            wheel_states=[],
        ),
        vision_coordinator=types.SimpleNamespace(
            clear_runtime=lambda: clear_calls.append("clear")
        ),
        _ensure_vision_coordinator=lambda: (_ for _ in ()).throw(
            AssertionError("should use public vision_coordinator")
        ),
    )

    ctx = TransportCommandContext(runtime, reply_uart=FakeUART(), source="uart6")

    ctx.reset_runtime()

    assert clear_calls == ["clear"]
