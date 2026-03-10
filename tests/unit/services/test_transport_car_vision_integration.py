"""TransportCar 视觉集成单元测试."""

import sys
import types
from typing import Any, cast

import pytest

from services.vision_protocol import VisionProtocol
from diagnostics.sink import UartSink
from diagnostics.manager import LogManager
from services.vision_debug import build_transition_event
from services.vision_state_defs import SM, SMState, VisionTransitionReason
from services.vision_state_machine import (
    VisionControlIntent,
    VisionResolvedTarget,
    VisionStepResult,
    VisionStateMachine,
)


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
    sys.modules.setdefault("machine", machine)

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
    sys.modules.setdefault("seekfree", seekfree)

    smartcar = types.ModuleType("smartcar")

    class FakeEncoder:
        def get(self):
            return 0

    def encoder(*_args, **_kwargs):
        return FakeEncoder()

    setattr(smartcar, "encoder", encoder)
    sys.modules.setdefault("smartcar", smartcar)


_install_transport_stubs()

from services.transport_car import TransportCar  # noqa: E402


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


class FakeOdometry:
    """测试里程计假对象."""

    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y


def build_transport_car():
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.uart3 = FakeUART()
    car.uart6 = FakeUART()
    car.logger_manager = LogManager(sinks=[UartSink(car.uart3)])
    car.log_vision = car.logger_manager.get_logger("vision.state")
    car.log_command = car.logger_manager.get_logger("services.command")
    car.log_health = car.logger_manager.get_logger("system.health")
    car._router = FakeRouter()
    car.vision_protocol = VisionProtocol(timeout_ms=200)
    car.vision_state_machine = FakeVisionMachine(
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
    car._vision_step_result = None
    car._vision_resolved_target = None
    car.heading_est = 90.0
    car.odometry = FakeOdometry(x=2.0, y=3.0)
    car.command_lock = False
    car.rear_only_mode = False
    car.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    car.apply_calls = []
    car.apply_command = lambda line: car.apply_calls.append(line)
    car._now_ms = lambda: 1000
    return car


def test_uart6_xy_packet_updates_visual_observation() -> None:
    car = build_transport_car()

    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    observation = car.vision_protocol.get_observation(now_ms=1000)
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

    assert car.vision_protocol.get_observation(now_ms=1000) is None
    assert car.apply_calls == []


def test_uart6_mixed_legacy_visual_payload_is_swallowed_without_routing_command() -> (
    None
):
    car = build_transport_car()

    car._handle_uart_line("x=120,y=80,angle=0", source="uart6")

    assert car.vision_protocol.get_observation(now_ms=1000) is None
    assert car.apply_calls == []


def test_uart6_malformed_legacy_visual_payload_is_swallowed_without_routing_command() -> (
    None
):
    car = build_transport_car()

    car._handle_uart_line("x=1,y=bad", source="uart6")

    assert car.vision_protocol.get_observation(now_ms=1000) is None
    assert car.apply_calls == []


def test_uart6_non_visual_packet_falls_back_to_command_router() -> None:
    car = build_transport_car()

    car._handle_uart_line("vx=1", source="uart6")

    assert car.apply_calls == ["vx=1"]


def test_visual_control_overrides_manual_position_target_without_lock() -> None:
    car = build_transport_car()
    car._vision_resolved_target = VisionResolvedTarget(
        x=5.0,
        y=6.0,
        angle_deg=45.0,
        rear_only_mode=True,
    )

    cmd_x, cmd_y = car._get_active_position_targets()

    assert (cmd_x, cmd_y) == (5.0, 6.0)
    assert car._get_active_angle_command() == 45.0
    assert car._get_active_rear_only_mode() is True
    assert car.command_lock is False


def test_refresh_vision_target_resolves_absolute_command() -> None:
    car = build_transport_car()
    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    assert len(car.vision_state_machine.calls) == 1
    assert car._vision_resolved_target is not None
    assert round(car._vision_resolved_target.x, 6) == 2.0
    assert round(car._vision_resolved_target.y, 6) == 4.0
    assert car._vision_resolved_target.angle_deg == 105.0


def test_command_lock_blocks_visual_target_refresh() -> None:
    car = build_transport_car()
    car.command_lock = True
    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    car._refresh_vision_target(now_ms=1000)

    assert car.vision_state_machine.calls == []
    assert car.vision_state_machine.reset_called is True
    assert car._vision_resolved_target is None
    assert car.vision_protocol.get_observation(now_ms=1000) is None


def test_transport_car_reads_state_name_from_registry() -> None:
    car = build_transport_car()
    car.vision_state_machine.state = SM.ALIGN_DX

    assert car._get_vision_state_name() == "ALIGN_DX"


def test_transport_car_debug_sink_writes_formatted_text_to_uart3() -> None:
    car = build_transport_car()
    event = build_transition_event(
        old_state=SMState.ALIGN_DIST,
        transition=SM.ALIGN_ANGLE.ANGLE_ERROR_REENTRY,
        stable_counter=0,
    )

    car._emit_vision_debug(event)

    assert any("[vision.state" in msg for msg in car.uart3.messages)
    assert any("VSM TRANS ALIGN_DIST->ALIGN_ANGLE" in msg for msg in car.uart3.messages)
    assert all("DEBUG breakpoint triggered" not in msg for msg in car.uart3.messages)


def test_transport_car_has_no_debug_breakpoint_api() -> None:
    car = build_transport_car()

    assert hasattr(car, "debug") is False


def test_vision_state_machine_transition_logs_without_breakpoint_wait() -> None:
    car = build_transport_car()
    car.vision_state_machine = VisionStateMachine(
        car._build_vision_state_config(),
        debug_sink=car._emit_vision_debug,
    )

    car._handle_uart_line("left=180,top=20,right=220,bottom=240", source="uart6")
    car._refresh_vision_target(now_ms=1000)

    assert any("[vision.state" in msg for msg in car.uart3.messages)
    assert any("VSM TRANS IDLE->ALIGN_ANGLE" in msg for msg in car.uart3.messages)
    assert all("DEBUG breakpoint triggered" not in msg for msg in car.uart3.messages)
