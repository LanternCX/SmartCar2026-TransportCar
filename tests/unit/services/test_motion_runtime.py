"""MotionRuntime 单元测试."""

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


_install_transport_stubs()


class FakeUart:
    """最小 UART 写口桩."""

    def __init__(self) -> None:
        self.messages = []

    def write(self, text: str) -> None:
        self.messages.append(text)


def test_motion_runtime_owns_chassis_and_pid_chain() -> None:
    from services.runtime.motion_runtime import MotionRuntime

    motion = MotionRuntime(
        diagnostic_mode=True,
        uart_writer=FakeUart(),
        load_ident_lookup_func=lambda _path: {},
        load_gyro_offsets_func=lambda _path: [0.0] * 6,
    )

    assert motion.chassis_state is not None
    assert motion.controller is not None
    assert motion.imu.get() == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert sorted(state["name"] for state in motion.chassis_state.wheel_states) == [
        "l",
        "m",
        "r",
    ]
