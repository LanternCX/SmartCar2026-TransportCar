"""TransportCar debug 断点单元测试."""

import sys
import types
from typing import Any, cast

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
from services.vision_protocol import VisionProtocol  # noqa: E402


class FakeUART:
    """测试串口假对象."""

    def __init__(self, chunks=None):
        self.messages = []
        self.any_calls = 0
        self.read_calls = 0
        self._chunks = []
        for chunk in chunks or []:
            if isinstance(chunk, bytes):
                self._chunks.append(chunk)
            else:
                self._chunks.append(chunk.encode())

    def write(self, text):
        self.messages.append(text)

    def any(self):
        self.any_calls += 1
        if not self._chunks:
            return 0
        return len(self._chunks[0])

    def read(self, _size):
        self.read_calls += 1
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class FakeMotor:
    """测试电机假对象."""

    def __init__(self):
        self.duty_calls = []

    def duty(self, value):
        self.duty_calls.append(value)


class FakeController:
    """测试速度环控制器假对象."""

    def __init__(self):
        self.reset_called = False

    def reset(self):
        self.reset_called = True


class FakeYawPID:
    """测试偏航控制器假对象."""

    def __init__(self):
        self.reset_called = False

    def reset(self):
        self.reset_called = True


class FakeSwitch:
    """测试急停开关假对象."""

    def __init__(self, value=1):
        self._value = value

    def value(self):
        return self._value


class FakeRouter:
    """测试路由器假对象."""

    def __init__(self):
        self.queries = []

    def handle_query(self, token, ctx, source="uart6"):
        self.queries.append((token, ctx, source))


def build_transport_car(uart3_chunks=None, uart6_chunks=None, now_us=43210):
    car = cast(Any, TransportCar.__new__(TransportCar))
    car.uart3 = FakeUART(uart3_chunks)
    car.uart6 = FakeUART(uart6_chunks)
    car.rx_buf3 = ""
    car.rx_buf6 = ""
    car.switch2 = FakeSwitch()
    car.switch2_init = 1
    car._router = FakeRouter()
    car.apply_calls = []
    car.apply_command = lambda line: car.apply_calls.append(line)
    car._debug_waiting = False
    car._debug_resume_requested = False
    car._now_ms = lambda: 0
    car.vision_protocol = types.SimpleNamespace(
        try_parse_observation=lambda *_args, **_kwargs: None
    )
    car.yaw_pid = FakeYawPID()
    car.yaw_integral = 3.5
    car.pit_flag = True
    car.last_time_us = 1000
    car._now_us = lambda: now_us
    car.wheel_states = []
    for _ in range(3):
        car.wheel_states.append(
            {"motor": FakeMotor(), "controller": FakeController(), "duty": 12.0}
        )
    return car


def test_debug_waits_for_uart3_resume_and_zeroes_motor_outputs() -> None:
    car = build_transport_car(uart3_chunks=["debug=1\n"])

    resumed = car.debug()

    assert resumed is True
    assert car._debug_waiting is False
    assert car._debug_resume_requested is False
    assert [state["duty"] for state in car.wheel_states] == [0.0, 0.0, 0.0]
    assert car.uart3.messages == [
        "DEBUG wait: send debug=1 on uart3 to resume.\r\n",
        "DEBUG resume.\r\n",
    ]
    for state in car.wheel_states:
        assert state["motor"].duty_calls == [0]


def test_debug_wait_ignores_non_resume_uart3_lines() -> None:
    car = build_transport_car(uart3_chunks=["?health\nvx=1\ndebug=1\n"])

    resumed = car.debug()

    assert resumed is True
    assert car._router.queries == []
    assert car.apply_calls == []


def test_debug_wait_resets_control_state_before_resume() -> None:
    car = build_transport_car(uart3_chunks=["debug=1\n"])

    car.debug()

    assert car.yaw_pid.reset_called is True
    assert car.yaw_integral == 0.0
    for state in car.wheel_states:
        assert state["controller"].reset_called is True


def test_debug_wait_rebases_tick_timing_before_resume() -> None:
    car = build_transport_car(uart3_chunks=["debug=1\n"], now_us=987654)

    car.debug()

    assert car.pit_flag is False
    assert car.last_time_us == 987654


def test_debug_wait_discards_uart6_traffic_without_applying_it() -> None:
    car = build_transport_car(
        uart3_chunks=["debug=1\n"],
        uart6_chunks=["vx=1\n"],
    )

    car.debug()
    car._process_uart()

    assert car.uart6.read_calls == 1
    assert car.apply_calls == []


def test_debug_wait_discards_partial_uart3_noise_before_resume_line() -> None:
    car = build_transport_car(uart3_chunks=["noise"])
    car._debug_waiting = True

    car._poll_debug_resume_uart()

    assert car.rx_buf3 == ""
    assert car._debug_resume_requested is False

    car.uart3 = FakeUART(["debug=1\n"])
    car._poll_debug_resume_uart()

    assert car._debug_resume_requested is True


def test_uart6_debug_token_does_not_release_waiting_state() -> None:
    car = build_transport_car()
    car._debug_waiting = True

    car._handle_uart_line("debug=1", source="uart6")

    assert car._debug_resume_requested is False


def test_debug_wait_keeps_latest_observation_alive_across_pause() -> None:
    car = build_transport_car(uart3_chunks=["debug=1\n"])
    now_values = iter([1000, 1600])
    car._now_ms = lambda: next(now_values)
    car.vision_protocol = VisionProtocol(timeout_ms=120)
    car.vision_protocol.try_parse_observation(
        "left=145,top=20,right=185,bottom=90", source="uart6", now_ms=950
    )

    car.debug()

    observation = car.vision_protocol.get_observation(now_ms=1600)

    assert observation is not None
    assert observation.timestamp_ms == 1550
