"""Fakes used by contract tests for command handlers."""

from typing import Optional


class FakeUART:
    """Collect UART writes for assertions."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class FakeOdometry:
    """Odometry fake with reset tracking."""

    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y
        self.reset_called = False

    def reset(self):
        self.x = 0.0
        self.y = 0.0
        self.reset_called = True


class FakeYawPID:
    """Yaw PID fake with reset tracking."""

    def __init__(self):
        self.reset_called = False

    def reset(self):
        self.reset_called = True


class FakeLPF:
    """Low pass filter fake with reset tracking."""

    def __init__(self):
        self.last_reset_value = None

    def reset(self, value=None):
        self.last_reset_value = value


class FakeController:
    """Controller fake used inside wheel states."""

    def __init__(self):
        self.reset_called = False

    def reset(self):
        self.reset_called = True


class FakeQuaternion:
    """Quaternion-like container."""

    def __init__(self):
        self.w = 0.0
        self.x = 1.0
        self.y = 2.0
        self.z = 3.0


class FakeVisionProtocol:
    """视觉协议假对象."""

    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class FakeVisionStateMachine:
    """视觉状态机假对象."""

    def __init__(self):
        self.reset_called = False

    def reset(self):
        self.reset_called = True


class FakeCommandContext:
    """Minimal context for motion and query handlers."""

    def __init__(self):
        self.command_lock = False
        self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self._pending_dx: Optional[float] = None
        self._pending_dy: Optional[float] = None
        self._pending_d_angle: Optional[float] = None
        self._rear_mode_changed = False
        self.rear_only_mode = False
        self.uart3 = FakeUART()
        self.uart6 = FakeUART()
        self.odometry = FakeOdometry()
        self.heading_est = 0.0
        self.heading_target = 0.0
        self.yaw_pid = FakeYawPID()
        self.yaw_integral = 0.0
        self.q_est = FakeQuaternion()
        self.last_yaw_rad = 0.0
        self.gyro_lpf = FakeLPF()
        self.vision_protocol = FakeVisionProtocol()
        self.vision_state_machine = FakeVisionStateMachine()
        self._vision_step_result = object()
        self._vision_resolved_target = object()
        self._query_response_uart = self.uart6
        self.wheel_states = [
            {"controller": FakeController(), "duty": 9.0},
            {"controller": FakeController(), "duty": -3.0},
        ]
        self.build_health_snapshot = lambda: {}
        self.build_tick_snapshot = lambda: {}
        self.build_imu_snapshot = lambda: {}
        self.build_encoder_snapshot = lambda: {}
        self.build_motor_snapshot = lambda: {}
        self.build_vision_snapshot = lambda: {}

    def get_query_uart(self):
        """返回当前查询响应应写入的串口."""
        return getattr(self, "_query_response_uart", self.uart6)
