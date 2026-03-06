"""Fakes used by contract tests for command handlers."""


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


class FakeCommandContext:
    """Minimal context for motion and query handlers."""

    def __init__(self):
        self.command_lock = False
        self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self._pending_dx = None
        self._pending_dy = None
        self._pending_d_angle = None
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
        self.wheel_states = [
            {"controller": FakeController(), "duty": 9.0},
            {"controller": FakeController(), "duty": -3.0},
        ]
