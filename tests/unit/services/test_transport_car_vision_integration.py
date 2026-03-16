"""TransportCar 视觉集成单元测试."""

import sys
import types
from typing import Any, cast

import pytest

from vision.protocol import VisionProtocol
from vision.coordinator import VisionCoordinator
from vision.runtime import VisionRuntime
from diagnostics.sink import UartSink
from diagnostics.manager import LogManager
from vision.debug import build_transition_event
from vision.state_defs import SM, SMState, VisionTransitionReason
from vision.state_machine import (
    VisionControlIntent,
    VisionStepResult,
    VisionStateConfig,
    VisionStateMachine,
)
from vision.transforms import VisionResolvedTarget


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

import services.car as transport_car_module  # noqa: E402
from services.car import TransportCar  # noqa: E402
from control.chassis_state import ChassisState  # noqa: E402
from services.commanding.session import CommandSession  # noqa: E402


class FakeUART:
    """测试串口假对象."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class FakeRouter:
    """测试路由器假对象."""

    def __init__(self):
        self.queries = []

    def handle_query(self, token, ctx):
        self.queries.append((token, ctx))


class FakeVisionMachine:
    """测试视觉状态机假对象."""

    def __init__(self, result):
        self.result = result
        self.calls = []
        self.reset_called = False

    def step(self, inputs):
        self.calls.append(inputs)
        return self.result

    def reset(self):
        self.reset_called = True


class FakeVisionCoordinator:
    """测试视觉协调器假对象."""

    protocol: Any
    state_machine: Any

    def __init__(self):
        self.consume_calls = []
        self.refresh_calls = []
        self.step_result = None
        self.resolved_target = cast(Any, None)
        self.next_resolved_target = cast(Any, None)
        self.next_released_heading_lock = False
        self.last_selected_input = None
        self.protocol = types.SimpleNamespace(get_observation=lambda now_ms: None)
        self.state_machine = types.SimpleNamespace(state=SM.ALIGN_DX)

    def consume_uart_line(self, line, source, now_ms):
        self.consume_calls.append((line, source, now_ms))
        return line.startswith("left=")

    def refresh(
        self,
        now_ms,
        heading_deg,
        odom_x,
        odom_y,
        command_lock,
        selected_input=None,
    ):
        self.refresh_calls.append((now_ms, heading_deg, odom_x, odom_y, command_lock))
        self.last_selected_input = selected_input
        self.resolved_target = self.next_resolved_target
        return types.SimpleNamespace(
            step_result=self.step_result,
            resolved_target=self.resolved_target,
            released_heading_lock=self.next_released_heading_lock,
        )

    def get_state_name(self):
        return "ALIGN_DX"

    def build_snapshot(self, now_ms):
        snapshot = {
            "state": self.get_state_name(),
            "obs_age_ms": None,
            "obs_left": None,
            "obs_top": None,
            "obs_right": None,
            "obs_bottom": None,
            "obs_center_x": None,
            "obs_center_y": None,
            "target_x": None,
            "target_y": None,
            "target_angle": None,
        }
        _ = now_ms
        if self.resolved_target is not None:
            snapshot["target_x"] = float(self.resolved_target.x)
            snapshot["target_y"] = float(self.resolved_target.y)
            snapshot["target_angle"] = float(self.resolved_target.angle_deg)
        return snapshot


class FakeOdometry:
    """测试里程计假对象."""

    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y


def build_transport_car():
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.uart3 = FakeUART()
    car.uart6 = FakeUART()
    car._active_vision_target_role = None
    car.logger_manager = LogManager(sinks=[UartSink(cast(Any, car.uart3))])
    car.log_vision = car.logger_manager.get_logger("vision.state")
    car.log_command = car.logger_manager.get_logger("services.command")
    car.log_health = car.logger_manager.get_logger("system.health")
    car._router = FakeRouter()
    vision_protocol = VisionProtocol(timeout_ms=200)
    vision_state_machine = FakeVisionMachine(
        VisionStepResult(
            state=1,
            intent=VisionControlIntent(
                active=True,
                dx_body=1.0,
                dy_body=0.0,
                d_angle_deg=15.0,
                rear_only_mode=False,
            ),
        )
    )
    car.vision_coordinator = VisionCoordinator(
        protocol=vision_protocol,
        state_machine=vision_state_machine,
    )
    car._command_session = CommandSession()
    car.command_session.command_lock = False
    car.command_session.rear_only_mode = False
    car.command_session.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    car.chassis_state = ChassisState(
        heading_est=90.0,
        odometry=FakeOdometry(x=2.0, y=3.0),
    )
    car.apply_calls = []
    car.apply_command = lambda line, source="uart6": car.apply_calls.append(
        (source, line)
    )
    car._now_ms = lambda: 1000
    car.now_ms = car._now_ms
    car.inverse_kinematics = lambda vx, vy, omega: (vx, vy, omega)
    return car


def _vision_protocol(car):
    return car.vision_coordinator.protocol


def build_runtime_backed_coordinator():
    runtime = VisionRuntime(timeout_ms=200)
    protocol = VisionProtocol(runtime)
    state_machine = FakeVisionMachine(
        VisionStepResult(
            state=int(SM.IDLE),
            intent=VisionControlIntent(
                active=False,
                dx_body=0.0,
                dy_body=0.0,
                d_angle_deg=0.0,
                rear_only_mode=False,
            ),
        )
    )
    cast(Any, state_machine).state = SM.IDLE
    coordinator = VisionCoordinator(
        protocol=protocol,
        state_machine=state_machine,
    )
    return coordinator, runtime


def _vision_state_machine(car):
    return car.vision_coordinator.state_machine


def _vision_frame(car, camera_id, now_ms=1000):
    return car.vision_coordinator.get_frame(camera_id, now_ms)


def _build_vision_state_config() -> VisionStateConfig:
    """构造测试使用的视觉状态机参数."""
    return VisionStateConfig(
        target_center_x_px=160.0,
        target_bottom_px=220.0,
        angle_kp=0.5,
        dist_kp=0.01,
        dx_kp=0.01,
        push_dx_kp=0.005,
        push_dy_m=0.1,
        push_distance_m=0.3,
        push_angle_deg=-90.0,
        angle_deadzone_px=5.0,
        angle_reentry_px=8.0,
        dist_deadzone_px=5.0,
        dx_deadzone_px=5.0,
        heading_tolerance_deg=5.0,
        stable_frames=2,
        max_dx_m=0.2,
        max_dy_m=0.2,
        max_d_angle_deg=30.0,
        done_hold_ms=100,
    )


def test_transport_car_uses_runtime_owner_without_legacy_vision_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    car = TransportCar(vehicle_role="main")
    assert getattr(car, "vision_service", None) is None
    assert getattr(car, "vision_coordinator", None) is None
    assert getattr(car, "vision_runtime", None) is None

    car._ensure_vision_coordinator()

    assert car.vision_service is not None
    assert "vision_runtime" in car.__dict__
    assert "vision_protocol" not in car.__dict__
    assert "vision_state_machine" not in car.__dict__
    assert "_vision_resolved_target" not in car.__dict__


def test_transport_car_uses_vision_service_for_aux_role_disabled_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    car = TransportCar(vehicle_role="aux")
    assert getattr(car, "vision_service", None) is None
    assert getattr(car, "vision_coordinator", None) is None

    car._ensure_vision_coordinator()

    assert car.vision_service is not None
    coordinator = cast(Any, car.vision_coordinator)

    assert car.vision_service.enabled is False
    assert car.vision_runtime is None
    assert coordinator.get_state_name() == "DISABLED"


def test_transport_car_builds_single_runtime_owner_for_vision_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    car = TransportCar(vehicle_role="main")
    assert getattr(car, "vision_coordinator", None) is None

    car._ensure_vision_coordinator()

    coordinator = cast(Any, car.vision_coordinator)

    assert coordinator.runtime is car.vision_runtime
    assert coordinator.protocol.runtime is car.vision_runtime


def test_transport_car_defers_vision_service_until_first_vision_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    car = TransportCar(vehicle_role="main")

    assert getattr(car, "vision_service", None) is None
    assert getattr(car, "vision_coordinator", None) is None
    assert getattr(car, "vision_runtime", None) is None

    coordinator = car._ensure_vision_coordinator()

    assert coordinator is car.vision_coordinator
    assert car.vision_service is not None
    assert car.vision_runtime is not None


def test_uart6_xy_packet_updates_visual_observation() -> None:
    car = build_transport_car()

    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    observation = _vision_protocol(car).get_observation(now_ms=1000)
    assert observation is not None
    assert observation.left == 100.0
    assert observation.top == 20.0
    assert observation.right == 140.0
    assert observation.bottom == 90.0
    assert observation.center_x == 120.0
    assert observation.center_y == 55.0
    assert car.apply_calls == []


def test_uart6_legacy_xy_packet_is_swallowed_without_routing_command() -> None:
    car = build_transport_car()

    car._handle_uart_line("x=120,y=80", source="uart6")

    assert _vision_protocol(car).get_observation(now_ms=1000) is None
    assert car.apply_calls == []


def test_uart6_mixed_legacy_visual_payload_is_swallowed_without_routing_command() -> (
    None
):
    car = build_transport_car()

    car._handle_uart_line("x=120,y=80,angle=0", source="uart6")

    assert _vision_protocol(car).get_observation(now_ms=1000) is None
    assert car.apply_calls == []


def test_uart6_malformed_legacy_visual_payload_is_swallowed_without_routing_command() -> (
    None
):
    car = build_transport_car()

    car._handle_uart_line("x=1,y=bad", source="uart6")

    assert _vision_protocol(car).get_observation(now_ms=1000) is None
    assert car.apply_calls == []


def test_uart6_non_visual_packet_falls_back_to_command_router() -> None:
    car = build_transport_car()

    car._handle_uart_line("vx=1", source="uart6")

    assert car.apply_calls == [("uart6", "vx=1")]


def test_apply_command_uses_explicit_source_when_building_handler_context() -> None:
    car = build_transport_car()
    routed = []

    class FakeRouter:
        def route(self, line, ctx):
            routed.append((line, ctx.source, ctx.reply_uart))
            return True

    car._router = FakeRouter()

    TransportCar.apply_command(car, "vx=1", source="uart3")

    assert routed == [("vx=1", "uart3", car.uart3)]


def test_handle_uart_line_delegates_uart6_visual_consumption_to_coordinator() -> None:
    car = build_transport_car()
    car.vision_coordinator = FakeVisionCoordinator()

    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    assert car.vision_coordinator.consume_calls == [
        ("left=100,top=20,right=140,bottom=90", "uart6", 1000)
    ]
    assert car.apply_calls == []


def test_visual_control_overrides_manual_position_target_without_lock() -> None:
    car = build_transport_car()
    car.vision_coordinator = FakeVisionCoordinator()
    car.vision_coordinator.resolved_target = VisionResolvedTarget(
        x=5.0,
        y=6.0,
        angle_deg=45.0,
        rear_only_mode=True,
    )

    cmd_x, cmd_y = car._get_active_position_targets()

    assert (cmd_x, cmd_y) == (5.0, 6.0)
    assert car._get_active_angle_command() == 45.0
    assert car._get_active_rear_only_mode() is True
    assert car.command_session.command_lock is False


def test_get_vision_resolved_target_prefers_runtime_owner() -> None:
    car = build_transport_car()
    runtime_target = VisionResolvedTarget(
        x=5.0,
        y=6.0,
        angle_deg=45.0,
        rear_only_mode=True,
    )
    car.vision_runtime = VisionRuntime(timeout_ms=200)
    cast(Any, car.vision_runtime).resolved_target = runtime_target
    car.vision_coordinator = FakeVisionCoordinator()
    car.vision_coordinator.resolved_target = VisionResolvedTarget(
        x=1.0,
        y=2.0,
        angle_deg=15.0,
        rear_only_mode=False,
    )

    assert car._get_vision_resolved_target() is runtime_target


def test_compute_planar_targets_prefers_vision_target_over_manual_position_target() -> (
    None
):
    car = build_transport_car()
    car.chassis_state.odometry = FakeOdometry(x=1.0, y=1.0)
    car.chassis_state.heading_est = 0.0
    car.chassis_state.kinematics = types.SimpleNamespace(
        velocity_m_s_to_pulses=lambda value, dt_s: value
    )
    car.command_session.last_cmd.update({"x": 100.0, "y": 100.0})
    car.vision_coordinator = FakeVisionCoordinator()
    car.vision_coordinator.resolved_target = VisionResolvedTarget(
        x=2.0,
        y=1.0,
        angle_deg=0.0,
        rear_only_mode=False,
    )

    target_vx_cmd, target_vy_cmd = car._compute_planar_targets(dt_s=0.01)

    assert target_vx_cmd != 0.0
    assert target_vy_cmd == 0.0
    assert abs(target_vx_cmd) < 1000.0


def test_handle_tick_refreshes_vision_before_other_control_steps() -> None:
    car = build_transport_car()
    order = []
    car._refresh_vision_target = lambda: order.append("vision")
    car.chassis_controller = types.SimpleNamespace(
        tick=lambda **_kwargs: order.append("control")
    )
    car.led = types.SimpleNamespace(toggle=lambda: order.append("led"))
    car.last_time_us = 1000000
    car.tick_count = 0
    car.loop_dt_total_us = 0
    car.max_loop_dt_us = 0
    car.loop_overrun_count = 0
    car._now_us = lambda: 1005000

    car._handle_tick()

    assert order.index("vision") < order.index("control")
    assert order[-1] == "control"


def test_transport_car_control_properties_delegate_to_chassis_state() -> None:
    car = build_transport_car()
    car.chassis_state = ChassisState(
        heading_est=12.0, heading_target=34.0, yaw_integral=5.0
    )

    car.chassis_state.heading_est = 45.0
    car.chassis_state.heading_target = 90.0
    car.chassis_state.yaw_integral = 6.0
    car.chassis_state.yaw_rate = 7.0
    car.chassis_state.last_gz_raw = 8.0

    assert car.chassis_state.heading_est == 45.0
    assert car.chassis_state.heading_target == 90.0
    assert car.chassis_state.yaw_integral == 6.0
    assert car.chassis_state.yaw_rate == 7.0
    assert car.chassis_state.last_gz_raw == 8.0


def test_transport_car_no_longer_exposes_command_or_chassis_compatibility_properties() -> (
    None
):
    removed_names = (
        "last_cmd",
        "command_lock",
        "lock_start_time",
        "rear_only_mode",
        "last_rear_mode",
        "wheel_states",
        "target_speeds",
        "yaw_pid",
        "heading_est",
        "heading_target",
        "yaw_integral",
        "odometry",
        "kinematics",
        "gyro_lpf",
        "q_est",
        "last_yaw_rad",
        "imu",
        "imu_data",
        "imu_offsets",
        "_yaw_rate",
        "_last_gz_raw",
    )

    for name in removed_names:
        assert hasattr(TransportCar, name) is False


def test_transport_car_composes_subsystems_without_owning_command_or_vision_private_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setattr(
        transport_car_module,
        "load_ident_lookup",
        lambda _path: {},
    )
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    car = TransportCar(vehicle_role="main")
    assert car.vision_processing_enabled is True
    car.command_session.pending_dx = 0.1
    car._ensure_vision_coordinator()
    cast(Any, car.vision_coordinator).resolved_target = VisionResolvedTarget(
        x=1.0,
        y=2.0,
        angle_deg=30.0,
        rear_only_mode=True,
    )

    assert "_command_session" in car.__dict__
    assert "vision_coordinator" in car.__dict__
    assert hasattr(TransportCar, "_pending_dx") is False
    assert hasattr(TransportCar, "_pending_dy") is False
    assert hasattr(TransportCar, "_pending_d_angle") is False
    assert hasattr(TransportCar, "_rear_mode_changed") is False
    assert hasattr(TransportCar, "_get_vision_step_result") is False
    assert "_query_response_uart" not in car.__dict__
    assert "_vision_resolved_target" not in car.__dict__
    assert "vision_protocol" not in car.__dict__
    assert "vision_state_machine" not in car.__dict__
    assert "rx_buf3" not in car.__dict__
    assert "rx_buf6" not in car.__dict__
    assert car.command_session.pending_dx == 0.1
    assert car._get_active_position_targets() == (1.0, 2.0)


def test_transport_car_rebuilds_missing_vision_coordinator_without_legacy_visual_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    car = TransportCar(vehicle_role="main")
    assert car.vision_processing_enabled is True
    car._ensure_vision_coordinator()
    legacy_protocol = object()
    legacy_state_machine = object()
    car.__dict__["vision_protocol"] = legacy_protocol
    car.__dict__["vision_state_machine"] = legacy_state_machine
    del car.vision_coordinator

    coordinator = car._ensure_vision_coordinator()

    assert coordinator.protocol is not legacy_protocol
    assert coordinator.state_machine is not legacy_state_machine


def test_refresh_vision_target_resolves_absolute_command() -> None:
    car = build_transport_car()
    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    assert len(_vision_state_machine(car).calls) == 1
    assert car.vision_coordinator.resolved_target is not None
    assert round(car.vision_coordinator.resolved_target.x, 6) == 2.0
    assert round(car.vision_coordinator.resolved_target.y, 6) == 4.0
    assert car.vision_coordinator.resolved_target.angle_deg == 105.0


def test_main_vehicle_polls_cameras_and_builds_observation_batches() -> None:
    car = build_transport_car()

    car._poll_vision_cameras()
    car._handle_uart_line(
        "camera_id=cam_b,frame_id=7,category=obstacle,left=10,top=20,right=50,bottom=80",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_b,frame_id=7,frame_end=1", source="uart6")
    car._handle_uart_line(
        "camera_id=cam_a,frame_id=11,category=cargo,left=100,top=20,right=140,bottom=90",
        source="uart6",
    )
    car._handle_uart_line(
        "camera_id=cam_a,frame_id=11,category=follower,left=150,top=25,right=190,bottom=95",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=11,frame_end=1", source="uart6")

    obstacle_frame = _vision_frame(car, "cam_b")
    cargo_frame = _vision_frame(car, "cam_a")

    assert car.uart6.messages == ["?frame=cam_b\r\n", "?frame=cam_a\r\n"]
    assert obstacle_frame is not None
    assert obstacle_frame.camera_id == "cam_b"
    assert obstacle_frame.frame_id == "7"
    assert [item.category for item in obstacle_frame.detections] == ["obstacle"]
    assert cargo_frame is not None
    assert cargo_frame.camera_id == "cam_a"
    assert cargo_frame.frame_id == "11"
    assert [item.category for item in cargo_frame.detections] == ["cargo", "follower"]


def test_transport_car_prefers_obstacle_camera_when_poll_budget_is_tight() -> None:
    car = build_transport_car()

    polled = car._poll_vision_cameras(poll_budget=1)

    assert polled == ["cam_b"]
    assert car.uart6.messages == ["?frame=cam_b\r\n"]


def test_transport_car_reuses_constant_camera_poll_order_tuple() -> None:
    car = build_transport_car()

    first = car._get_vision_camera_poll_order()
    second = car._get_vision_camera_poll_order()

    assert first is transport_car_module.VISION_CAMERA_POLL_ORDER
    assert second is first


def test_poll_vision_cameras_reuses_cached_query_strings_on_hot_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    car = build_transport_car()
    build_calls = []

    def fake_build_frame_query(camera_id: str) -> str:
        build_calls.append(camera_id)
        return "?frame=%s" % camera_id

    monkeypatch.setattr(
        transport_car_module.VisionProtocol,
        "build_frame_query",
        staticmethod(fake_build_frame_query),
    )

    first = car._poll_vision_cameras()
    second = car._poll_vision_cameras()

    assert build_calls == ["cam_b", "cam_a"]
    assert first is transport_car_module.VISION_CAMERA_POLL_ORDER
    assert second is first
    assert car.uart6.messages == [
        "?frame=cam_b\r\n",
        "?frame=cam_a\r\n",
        "?frame=cam_b\r\n",
        "?frame=cam_a\r\n",
    ]


def test_refresh_vision_target_prefers_active_role_across_multiple_camera_frames() -> (
    None
):
    car = build_transport_car()
    car.chassis_state.heading_est = 0.0
    car.chassis_state.odometry = FakeOdometry(x=0.0, y=0.0)
    car.command_session.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    car._active_vision_target_role = "cargo"

    car._handle_uart_line(
        "camera_id=cam_b,frame_id=41,category=cargo,left=140,top=20,right=180,bottom=220",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_b,frame_id=41,frame_end=1", source="uart6")
    car._handle_uart_line(
        "camera_id=cam_a,frame_id=31,category=follower,left=150,top=25,right=190,bottom=220",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=31,frame_end=1", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    selected_target = car._get_vision_resolved_target()
    state_machine = _vision_state_machine(car)

    assert selected_target is not None
    assert car._active_vision_target_role == "cargo"
    assert state_machine.calls[-1].observation is not None
    assert state_machine.calls[-1].observation.category == "cargo"
    assert state_machine.calls[-1].observation.camera_id == "cam_b"


def test_select_vision_state_machine_input_prefers_runtime_owner_frames() -> None:
    car = build_transport_car()
    runtime = VisionRuntime(timeout_ms=200)
    protocol = VisionProtocol(runtime)
    car.vision_runtime = runtime
    car.vision_coordinator = FakeVisionCoordinator()
    car._active_vision_target_role = "cargo"

    protocol.try_parse_observation(
        "camera_id=cam_b,frame_id=41,category=cargo,left=140,top=20,right=180,bottom=220",
        source="uart6",
        now_ms=990,
    )
    protocol.try_parse_observation(
        "camera_id=cam_b,frame_id=41,frame_end=1",
        source="uart6",
        now_ms=991,
    )
    protocol.try_parse_observation(
        "camera_id=cam_a,frame_id=31,category=follower,left=150,top=25,right=190,bottom=220",
        source="uart6",
        now_ms=992,
    )
    protocol.try_parse_observation(
        "camera_id=cam_a,frame_id=31,frame_end=1",
        source="uart6",
        now_ms=993,
    )

    selected_input = car._select_vision_state_machine_input(now_ms=1000)

    assert selected_input.target_role == "cargo"
    assert selected_input.observation is not None
    assert selected_input.observation.category == "cargo"
    assert selected_input.observation.camera_id == "cam_b"


def test_overlapping_category_from_two_cameras_uses_priority_camera_before_score_tie_break() -> (
    None
):
    car = build_transport_car()
    car.chassis_state.heading_est = 0.0
    car.chassis_state.odometry = FakeOdometry(x=0.0, y=0.0)
    car.command_session.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}

    car._handle_uart_line(
        "camera_id=cam_a,frame_id=51,category=follower,left=140,top=20,right=180,bottom=170",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=51,frame_end=1", source="uart6")
    car._handle_uart_line(
        "camera_id=cam_b,frame_id=52,category=follower,left=100,top=10,right=220,bottom=230",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_b,frame_id=52,frame_end=1", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    state_machine = _vision_state_machine(car)

    assert car._active_vision_target_role == "follower"
    assert state_machine.calls[-1].observation is not None
    assert state_machine.calls[-1].observation.category == "follower"
    assert state_machine.calls[-1].observation.camera_id == "cam_a"


def test_unselected_detections_do_not_override_active_transport_intent() -> None:
    car = build_transport_car()
    car.chassis_state.heading_est = 0.0
    car.chassis_state.odometry = FakeOdometry(x=0.0, y=0.0)
    car.command_session.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}

    car._handle_uart_line(
        "camera_id=cam_a,frame_id=11,category=follower,left=150,top=25,right=190,bottom=220",
        source="uart6",
    )
    car._handle_uart_line(
        "camera_id=cam_a,frame_id=11,category=cargo,left=10,top=20,right=50,bottom=90",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=11,frame_end=1", source="uart6")

    car._refresh_vision_target(now_ms=1000)
    selected_target = car._get_vision_resolved_target()
    state_machine = _vision_state_machine(car)

    assert selected_target is not None
    assert car._active_vision_target_role == "follower"
    assert round(selected_target.x, 6) == 1.0
    assert state_machine.calls[-1].observation.category == "follower"

    car._handle_uart_line(
        "camera_id=cam_a,frame_id=12,category=cargo,left=240,top=20,right=280,bottom=220",
        source="uart6",
    )
    car._handle_uart_line(
        "camera_id=cam_a,frame_id=12,category=follower,left=10,top=20,right=50,bottom=90",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=12,frame_end=1", source="uart6")

    car._refresh_vision_target(now_ms=1010)
    selected_target = car._get_vision_resolved_target()

    assert selected_target is not None
    assert car._active_vision_target_role == "follower"
    assert state_machine.calls[-1].observation.category == "follower"


def test_missing_active_target_role_does_not_retarget_to_other_detection() -> None:
    car = build_transport_car()
    car.chassis_state.heading_est = 0.0
    car.chassis_state.odometry = FakeOdometry(x=0.0, y=0.0)
    car._active_vision_target_role = "follower"
    protocol = _vision_protocol(car)
    car.vision_coordinator = VisionCoordinator(
        protocol=protocol,
        state_machine=FakeVisionMachine(
            VisionStepResult(
                state=int(SM.IDLE),
                intent=VisionControlIntent(
                    active=False,
                    dx_body=0.0,
                    dy_body=0.0,
                    d_angle_deg=0.0,
                    rear_only_mode=False,
                ),
            )
        ),
    )

    car._handle_uart_line(
        "camera_id=cam_a,frame_id=21,category=cargo,left=240,top=20,right=280,bottom=220",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=21,frame_end=1", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    state_machine = _vision_state_machine(car)
    assert car._active_vision_target_role == "follower"
    assert state_machine.calls[-1].observation is None
    assert state_machine.calls[-1].target_role == "follower"
    assert car.vision_coordinator.step_result is not None
    assert car.vision_coordinator.step_result.intent.active is False
    assert car.vision_coordinator.resolved_target is None


def test_state_machine_input_does_not_fall_back_to_raw_observation_cache() -> None:
    car = build_transport_car()
    car.chassis_state.heading_est = 0.0
    car.chassis_state.odometry = FakeOdometry(x=0.0, y=0.0)
    car._active_vision_target_role = "follower"
    protocol = _vision_protocol(car)
    car.vision_coordinator = VisionCoordinator(
        protocol=protocol,
        state_machine=FakeVisionMachine(
            VisionStepResult(
                state=int(SM.IDLE),
                intent=VisionControlIntent(
                    active=False,
                    dx_body=0.0,
                    dy_body=0.0,
                    d_angle_deg=0.0,
                    rear_only_mode=False,
                ),
            )
        ),
    )

    protocol.try_parse_observation(
        "left=120,top=20,right=160,bottom=220", source="uart6", now_ms=1000
    )
    car._handle_uart_line(
        "camera_id=cam_a,frame_id=22,category=cargo,left=240,top=20,right=280,bottom=220",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=22,frame_end=1", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    state_machine = _vision_state_machine(car)
    assert state_machine.calls[-1].observation is None
    assert state_machine.calls[-1].target_role == "follower"
    assert car.vision_coordinator.step_result is not None
    assert car.vision_coordinator.step_result.intent.active is False
    assert car.vision_coordinator.resolved_target is None


def test_selected_none_is_passed_to_state_machine_without_raw_cache_fallback() -> None:
    car = build_transport_car()
    car.chassis_state.heading_est = 0.0
    car.chassis_state.odometry = FakeOdometry(x=0.0, y=0.0)
    car._active_vision_target_role = "follower"
    protocol = _vision_protocol(car)
    recorded_inputs = []

    class RecordingMachine:
        def __init__(self):
            self.state = SM.IDLE

        def step(self, inputs):
            recorded_inputs.append(inputs)
            return VisionStepResult(
                state=int(SM.IDLE),
                intent=VisionControlIntent(
                    active=False,
                    dx_body=0.0,
                    dy_body=0.0,
                    d_angle_deg=0.0,
                    rear_only_mode=False,
                ),
            )

        def reset(self):
            return None

    car.vision_coordinator = VisionCoordinator(
        protocol=protocol,
        state_machine=RecordingMachine(),
    )

    protocol.try_parse_observation(
        "left=120,top=20,right=160,bottom=220", source="uart6", now_ms=1000
    )
    car._handle_uart_line(
        "camera_id=cam_a,frame_id=23,category=cargo,left=240,top=20,right=280,bottom=220",
        source="uart6",
    )
    car._handle_uart_line("camera_id=cam_a,frame_id=23,frame_end=1", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    assert recorded_inputs[-1].observation is None
    assert recorded_inputs[-1].target_role == "follower"


def test_command_lock_blocks_visual_target_refresh() -> None:
    car = build_transport_car()
    car.command_session.command_lock = True
    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    assert _vision_state_machine(car).calls == []
    assert _vision_state_machine(car).reset_called is True
    assert car.vision_coordinator.resolved_target is None
    assert _vision_protocol(car).get_observation(now_ms=1000) is None


def test_vision_coordinator_resets_observation_when_manual_lock_is_active() -> None:
    coordinator = VisionCoordinator(
        protocol=VisionProtocol(timeout_ms=200),
        state_machine=FakeVisionMachine(
            VisionStepResult(
                state=1,
                intent=VisionControlIntent(
                    active=True,
                    dx_body=1.0,
                    dy_body=0.0,
                    d_angle_deg=15.0,
                    rear_only_mode=False,
                ),
            )
        ),
    )
    coordinator.consume_uart_line(
        "left=100,top=20,right=140,bottom=90", source="uart6", now_ms=1000
    )

    refresh_result = coordinator.refresh(
        now_ms=1000,
        heading_deg=90.0,
        odom_x=2.0,
        odom_y=3.0,
        command_lock=True,
    )

    assert refresh_result.resolved_target is None
    assert coordinator.state_machine.reset_called is True
    assert coordinator.get_observation(now_ms=1000) is None


def test_coordinator_build_snapshot_reads_runtime_buffer() -> None:
    coordinator, runtime = build_runtime_backed_coordinator()

    protocol = coordinator.protocol
    protocol.try_parse_observation(
        "camera_id=cam_a,frame_id=31,category=follower,left=100,top=20,right=140,bottom=90",
        source="uart6",
        now_ms=980,
    )
    protocol.try_parse_observation(
        "camera_id=cam_a,frame_id=31,frame_end=1", source="uart6", now_ms=980
    )
    cast(Any, runtime).selected_input = types.SimpleNamespace(
        observation=runtime.latest_observation
    )
    cast(Any, runtime).resolved_target = VisionResolvedTarget(
        x=2.0,
        y=3.0,
        angle_deg=15.0,
        rear_only_mode=False,
    )

    snapshot = cast(Any, coordinator.build_snapshot(1000))

    assert snapshot["state"] == "IDLE"
    assert snapshot["obs_age_ms"] == 20
    assert snapshot["obs_left"] == 100.0
    assert snapshot["obs_center_x"] == 120.0
    assert snapshot["target_x"] == 2.0
    assert snapshot["target_angle"] == 15.0


def test_refresh_vision_target_delegates_to_coordinator() -> None:
    car = build_transport_car()
    coordinator = FakeVisionCoordinator()
    coordinator.resolved_target = VisionResolvedTarget(
        x=5.0,
        y=6.0,
        angle_deg=45.0,
        rear_only_mode=True,
    )
    coordinator.next_resolved_target = coordinator.resolved_target
    car.vision_coordinator = coordinator

    car._refresh_vision_target(now_ms=1000)

    assert coordinator.refresh_calls == [(1000, 90.0, 2.0, 3.0, False)]
    assert coordinator.last_selected_input is not None
    assert car._get_vision_resolved_target() == coordinator.resolved_target


def test_refresh_vision_target_does_not_swallow_typeerror_from_coordinator() -> None:
    car = build_transport_car()

    class BuggyCoordinator:
        def __init__(self):
            self.resolved_target = None
            self.step_result = None
            self.state_machine = types.SimpleNamespace(state=SM.IDLE)

        def get_frame(self, camera_id, now_ms):
            _ = (camera_id, now_ms)
            return None

        def get_observation(self, now_ms):
            _ = now_ms
            return None

        def refresh(
            self,
            now_ms,
            heading_deg,
            odom_x,
            odom_y,
            command_lock,
            selected_input=None,
        ):
            _ = (now_ms, heading_deg, odom_x, odom_y, command_lock)
            if selected_input is not None:
                raise TypeError("selected_input bug")
            return types.SimpleNamespace(
                step_result=None,
                resolved_target=None,
                released_heading_lock=False,
            )

        def get_state_name(self):
            return "IDLE"

        def build_snapshot(self, now_ms):
            _ = now_ms
            return {
                "state": "IDLE",
                "obs_age_ms": None,
                "obs_left": None,
                "obs_top": None,
                "obs_right": None,
                "obs_bottom": None,
                "obs_center_x": None,
                "obs_center_y": None,
                "target_x": None,
                "target_y": None,
                "target_angle": None,
            }

    car.vision_coordinator = BuggyCoordinator()

    with pytest.raises(TypeError, match="selected_input bug"):
        car._refresh_vision_target(now_ms=1000)


def test_transport_car_reads_state_name_from_registry() -> None:
    car = build_transport_car()
    _vision_state_machine(car).state = SM.ALIGN_DX

    assert car._get_vision_state_name() == "ALIGN_DX"


def test_transport_car_debug_sink_writes_formatted_text_to_uart3() -> None:
    car = build_transport_car()
    event = build_transition_event(
        old_state=SMState.ALIGN_DIST,
        transition=SM.ALIGN_ANGLE.ANGLE_ERROR_REENTRY,
        stable_counter=0,
    )

    car._emit_vision_debug(event)

    assert not any("[vision.state" in msg for msg in car.uart3.messages)
    assert not any(
        "VSM TRANS ALIGN_DIST->ALIGN_ANGLE" in msg for msg in car.uart3.messages
    )
    assert all("DEBUG breakpoint triggered" not in msg for msg in car.uart3.messages)


def test_transport_car_has_no_debug_breakpoint_api() -> None:
    car = build_transport_car()

    assert hasattr(car, "debug") is False


def test_compute_omega_cmd_keeps_visual_target_in_continuous_heading_domain() -> None:
    car = build_transport_car()
    car.chassis_state.heading_est = 270.0
    car.chassis_state.heading_target = 0.0
    car.chassis_state.yaw_rate = 0.0
    car.vision_coordinator = FakeVisionCoordinator()
    car.vision_coordinator.resolved_target = VisionResolvedTarget(
        x=2.0,
        y=3.0,
        angle_deg=-90.0,
        rear_only_mode=False,
    )

    class FakeYawPid:
        def __init__(self):
            self.calls = []
            self.integral = 0.0

        def update(self, target, now, dt_s):
            self.calls.append((target, now, dt_s))
            return target - now

    car.chassis_state.yaw_pid = FakeYawPid()

    omega_cmd = car._compute_omega_cmd(dt_s=0.01)

    assert omega_cmd == 0.0
    assert car.chassis_state.heading_target == 270.0
    assert car.chassis_state.yaw_pid.calls == [(270.0, 270.0, 0.01)]


def test_check_unlock_accepts_equivalent_wrapped_heading_and_clears_rear_mode() -> None:
    car = build_transport_car()
    car.command_session.command_lock = True
    car.command_session.rear_only_mode = True
    car.chassis_state.heading_target = -90.0
    car.chassis_state.heading_est = 270.0
    car.command_session.last_cmd = {"angle": -90.0}
    car.chassis_state.target_speeds = {"m": 1.0, "l": 2.0, "r": 3.0}
    car.chassis_state.odometry = FakeOdometry(x=0.0, y=0.0)

    class FakeResettable:
        def __init__(self):
            self.reset_called = False

        def reset(self):
            self.reset_called = True

    class FakeMotor:
        def __init__(self):
            self.values = []

        def duty(self, value):
            self.values.append(value)

    yaw_pid = FakeResettable()
    car.chassis_state.yaw_pid = yaw_pid
    car.chassis_state.yaw_integral = 5.0
    car.chassis_state.wheel_states = [
        {
            "motor": FakeMotor(),
            "duty": 100.0,
            "controller": FakeResettable(),
        }
        for _ in range(3)
    ]

    car._check_unlock()

    assert car.command_session.command_lock is False
    assert car.command_session.rear_only_mode is False
    assert car.command_session.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert car.chassis_state.heading_target == 270.0
    assert yaw_pid.reset_called is True
    assert car.chassis_state.yaw_integral == 0.0
    assert all(state["duty"] == 0.0 for state in car.chassis_state.wheel_states)
    assert all(
        state["motor"].values[-1] == 0 for state in car.chassis_state.wheel_states
    )
    assert car.uart3.messages[-1].startswith("Target Reached. Auto-revert Rear Mode")


def test_refresh_vision_target_releases_stale_heading_when_intent_turns_inactive() -> (
    None
):
    car = build_transport_car()
    car.chassis_state.heading_est = -80.2
    car.chassis_state.heading_target = -90.0
    car.chassis_state.yaw_integral = 4.0
    car.vision_coordinator = FakeVisionCoordinator()
    car.vision_coordinator.resolved_target = VisionResolvedTarget(
        x=0.0,
        y=0.0,
        angle_deg=-90.0,
        rear_only_mode=True,
    )
    car.vision_coordinator.next_resolved_target = None
    car.vision_coordinator.next_released_heading_lock = True
    car.vision_coordinator.state_machine = FakeVisionMachine(
        VisionStepResult(
            state=int(SM.ALIGN_DX),
            intent=VisionControlIntent(
                active=False,
                dx_body=0.0,
                dy_body=0.0,
                d_angle_deg=0.0,
                rear_only_mode=False,
            ),
        )
    )

    class FakeYawPid:
        def __init__(self):
            self.reset_called = False

        def reset(self):
            self.reset_called = True

    car.chassis_state.yaw_pid = FakeYawPid()
    car._handle_uart_line("left=140,top=20,right=160,bottom=219", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    assert car.vision_coordinator.resolved_target is None
    assert car.chassis_state.heading_target == -80.2
    assert car.chassis_state.yaw_integral == 0.0
    assert car.chassis_state.yaw_pid.reset_called is True


def test_vision_state_machine_transition_logs_without_breakpoint_wait() -> None:
    car = build_transport_car()
    protocol = _vision_protocol(car)
    state_machine = VisionStateMachine(
        car._build_vision_state_config(),
        debug_sink=car._emit_vision_debug,
    )
    car.vision_coordinator = VisionCoordinator(
        protocol=protocol,
        state_machine=state_machine,
    )

    car._handle_uart_line("left=180,top=20,right=220,bottom=240", source="uart6")
    car._refresh_vision_target(now_ms=1000)

    assert not any("VSM TRANS IDLE->ALIGN_ANGLE" in msg for msg in car.uart3.messages)


def test_vision_state_machine_transition_logs_in_debug_level() -> None:
    car = build_transport_car()
    car.logger_manager.set_level_name("DEBUG")
    event = build_transition_event(
        old_state=SM.IDLE,
        new_state=SM.ALIGN_ANGLE,
        reason=VisionTransitionReason.OBSERVATION_ACQUIRED,
        stable_counter=0,
        observation_x=24.5,
        observation_y=220.0,
        heading_deg=0.0,
        odom_x=0.0,
        odom_y=0.0,
        now_ms=1000,
    )

    car._emit_vision_debug(event)

    assert any("VSM TRANS IDLE->ALIGN_ANGLE" in msg for msg in car.uart3.messages)
    assert all("DEBUG breakpoint triggered" not in msg for msg in car.uart3.messages)
