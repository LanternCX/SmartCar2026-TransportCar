"""辅车底盘运行时边界.

@file src/assistant/ctrl/chassis.py
"""

from assistant.runtime_params import FOLLOW_TIMEOUT_MS
import assistant.runtime_params as runtime_params
from assistant.ctrl.kinematics import inverse_kinematics
from assistant.safety import SafetyGuard
from assistant.status import AssistantState, render_state


class CoreRuntime:
    def __init__(self, timeout_ms=None, hw_bundle=None):
        if timeout_ms is None:
            timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
        self.hw_bundle = hw_bundle
        self.state = AssistantState()
        self.safety = SafetyGuard(timeout_ms=timeout_ms)


class ChassisRuntime:
    def __init__(self, timeout_ms=None, hw_bundle=None):
        if timeout_ms is None:
            timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
        self.core = CoreRuntime(timeout_ms=timeout_ms, hw_bundle=hw_bundle)
        self.state = self.core.state
        self.safety = self.core.safety
        self.pid_map = dict(runtime_params.PID_MAP)
        self.speed_filter_window = int(runtime_params.SPEED_FILTER_WINDOW)
        self.speed_diff_max_delta = float(runtime_params.SPEED_DIFF_MAX_DELTA)
        self.gyro_lpf_alpha = float(runtime_params.GYRO_LPF_ALPHA)
        self.yaw_kp = float(runtime_params.YAW_KP)
        self.yaw_ki = float(runtime_params.YAW_KI)
        self.yaw_i_max = float(runtime_params.YAW_I_MAX)
        self.auto_omega_max = float(runtime_params.AUTO_OMEGA_MAX)
        self.target_heading_deg = 0.0
        self._yaw_integral = 0.0

    def _motor_bundle(self):
        if self.core.hw_bundle is None:
            return None
        return self.core.hw_bundle.get("motors")

    def _imu_bundle(self):
        if self.core.hw_bundle is None:
            return None
        return self.core.hw_bundle.get("imu")

    def _read_heading_deg(self):
        imu = self._imu_bundle()
        if imu is None:
            return 0.0
        getter = getattr(imu, "heading_deg", None)
        if getter is not None:
            return float(getter())
        getter = getattr(imu, "get", None)
        if getter is not None:
            return float(getter("heading_deg", 0.0))
        return 0.0

    def _compute_heading_correction(self):
        heading_deg = self._read_heading_deg()
        self.state.heading_deg = heading_deg
        error = self.target_heading_deg - heading_deg
        self._yaw_integral += error
        self._yaw_integral = max(
            -self.yaw_i_max, min(self.yaw_i_max, self._yaw_integral)
        )
        omega = error * self.yaw_kp + self._yaw_integral * self.yaw_ki
        return max(-self.auto_omega_max, min(self.auto_omega_max, omega))

    def _apply_motor_output(self, dx, dy, omega):
        motors = self._motor_bundle()
        if motors is None:
            return
        wheel_targets = inverse_kinematics(dx, dy, omega)
        limit = float(runtime_params.FOLLOW_OUTPUT_LIMIT)
        for name, motor in motors.items():
            raw = float(wheel_targets.get(name, 0.0))
            duty = int(max(-limit, min(limit, raw)))
            motor.set_duty(duty)

    def _stop_motors(self):
        motors = self._motor_bundle()
        if motors is None:
            return
        for motor in motors.values():
            stop = getattr(motor, "stop", None)
            if stop is not None:
                stop()
            else:
                motor.set_duty(0)

    def _stop(self, reason=""):
        self.state.follow_active = False
        self.state.state_label = "TIMEOUT" if reason == "timeout_stop" else "IDLE"
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.timeout = reason == "timeout_stop"
        self._stop_motors()
        if reason:
            self.state.last_error = reason

    def _preserve_timeout_stop(self):
        self.state.follow_active = False
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.state_label = "TIMEOUT"
        self.state.timeout = True
        self._stop_motors()
        self.state.last_error = "timeout_stop"

    def _is_timeout_locked(self):
        return bool(self.state.timeout) or self.state.state_label == "TIMEOUT"

    def _clear_follow_deadline(self):
        self.safety.last_command_ms = None

    def _reject_unsupported_command(self):
        if not self._is_timeout_locked():
            self.state.timeout = False
        self.state.last_error = "unsupported_command"
        return "ERR"

    def _apply_follow(self, command, now_ms):
        if int(command.seq) <= int(self.state.last_seq):
            return "IGNORED"

        self.safety.mark_command(now_ms)
        self.safety.clear_estop()
        self.state.last_error = ""
        self.state.timeout = False
        self.state.last_seq = int(command.seq)
        if not command.valid:
            self.state.follow_active = False
            self.state.state_label = "IDLE"
            self.state.velocity_command = (0.0, 0.0, 0.0)
            self._stop_motors()
            return "HOLD"

        self.state.follow_active = True
        self.state.state_label = "BUSY"
        limited_dx = max(
            -float(runtime_params.FOLLOW_OUTPUT_LIMIT),
            min(float(runtime_params.FOLLOW_OUTPUT_LIMIT), float(command.dx)),
        )
        limited_dy = max(
            -float(runtime_params.FOLLOW_OUTPUT_LIMIT),
            min(float(runtime_params.FOLLOW_OUTPUT_LIMIT), float(command.dy)),
        )
        self.state.velocity_command = (
            limited_dx,
            limited_dy,
            self._compute_heading_correction(),
        )
        self._apply_motor_output(
            self.state.velocity_command[0],
            self.state.velocity_command[1],
            self.state.velocity_command[2],
        )
        return "BUSY"

    def _apply_velocity(self, command, now_ms):
        self.safety.mark_command(now_ms)
        self.safety.clear_estop()
        self.state.last_error = ""
        self.state.timeout = False
        self.state.follow_active = True
        self.state.state_label = "BUSY"
        omega = float(command.omega) + self._compute_heading_correction()
        limited_omega = max(-self.auto_omega_max, min(self.auto_omega_max, omega))
        self.state.velocity_command = (
            float(command.vx),
            float(command.vy),
            limited_omega,
        )
        return "BUSY"

    def apply_command(self, command, now_ms):
        if command.kind == "ping":
            return "ACK"
        if command.kind == "state_query":
            return render_state(self.state)
        if command.kind == "follow":
            return self._apply_follow(command, now_ms)
        if command.kind == "arm":
            return "ACK"
        if command.kind == "disarm":
            self._clear_follow_deadline()
            if self._is_timeout_locked():
                self._preserve_timeout_stop()
            else:
                self._stop()
            return "ACK"
        if command.kind == "stop":
            self.safety.trigger_estop()
            if self._is_timeout_locked():
                self._preserve_timeout_stop()
            else:
                self._stop("estop")
            return "DONE"
        if command.kind == "reset_odom":
            self._clear_follow_deadline()
            self.state.odom[0] = 0.0
            self.state.odom[1] = 0.0
            self.state.heading_deg = 0.0
            self.state.follow_active = False
            self.state.state_label = "IDLE"
            self.state.velocity_command = (0.0, 0.0, 0.0)
            self.state.timeout = False
            self.state.last_error = ""
            self._stop_motors()
            self.safety.clear_estop()
            return "ACK"
        if command.kind == "hold":
            self._clear_follow_deadline()
            self.state.follow_active = False
            if not self._is_timeout_locked():
                self.state.state_label = "IDLE"
            self.state.velocity_command = (0.0, 0.0, 0.0)
            self._stop_motors()
            self.safety.clear_estop()
            return "DONE"
        if command.kind == "vel":
            return self._apply_velocity(command, now_ms)
        if command.kind == "move":
            return self._reject_unsupported_command()
        return self._reject_unsupported_command()

    def tick(self, now_ms):
        if self.safety.should_stop(now_ms):
            if self._is_timeout_locked():
                self._preserve_timeout_stop()
            else:
                reason = "estop" if self.safety.estop_active else "timeout_stop"
                self._stop(reason)
            return "DONE"
        if self.state.follow_active:
            return "BUSY"
        return "ACK"

    def state_line(self):
        return render_state(self.state)


MotionRuntime = ChassisRuntime
