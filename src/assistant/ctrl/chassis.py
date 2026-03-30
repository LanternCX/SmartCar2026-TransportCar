"""辅车底盘运行时边界.

@file src/assistant/ctrl/chassis.py
"""

from config.params import FOLLOW_TIMEOUT_MS
from assistant.safety import SafetyGuard
from assistant.status import AssistantState, render_state


class CoreRuntime:
    def __init__(self, timeout_ms=FOLLOW_TIMEOUT_MS, hw_bundle=None):
        self.hw_bundle = hw_bundle
        self.state = AssistantState()
        self.safety = SafetyGuard(timeout_ms=timeout_ms)


class ChassisRuntime:
    def __init__(self, timeout_ms=FOLLOW_TIMEOUT_MS, hw_bundle=None):
        self.core = CoreRuntime(timeout_ms=timeout_ms, hw_bundle=hw_bundle)
        self.state = self.core.state
        self.safety = self.core.safety

    def _stop(self, reason=""):
        self.state.follow_active = False
        self.state.state_label = "TIMEOUT" if reason == "timeout_stop" else "IDLE"
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.timeout = reason == "timeout_stop"
        if reason:
            self.state.last_error = reason

    def _preserve_timeout_stop(self):
        self.state.follow_active = False
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.state_label = "TIMEOUT"
        self.state.timeout = True
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
            return "HOLD"

        self.state.follow_active = True
        self.state.state_label = "BUSY"
        self.state.velocity_command = (command.dx, command.dy, 0.0)
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
            self.safety.clear_estop()
            return "ACK"
        if command.kind == "hold":
            self._clear_follow_deadline()
            self.state.follow_active = False
            if not self._is_timeout_locked():
                self.state.state_label = "IDLE"
            self.state.velocity_command = (0.0, 0.0, 0.0)
            self.safety.clear_estop()
            return "DONE"
        if command.kind == "vel":
            return self._reject_unsupported_command()
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
