"""辅车最小执行闭环

@file src/assistant/motion_runtime.py
"""

from config.params import FOLLOW_TIMEOUT_MS
from assistant.protocol import Command
from assistant.safety import SafetyGuard
from assistant.status import AssistantState, render_state
from assistant.stability.control import HeadingController
from assistant.stability.kinematics import rotate_body_delta_to_world


class MotionRuntime:
    """辅车最小执行运行时

    @brief 管理协议命令、最小状态与安全停机
    """

    def __init__(self, timeout_ms=FOLLOW_TIMEOUT_MS):
        self.state = AssistantState()
        self.safety = SafetyGuard(timeout_ms=timeout_ms)
        self.heading_controller = HeadingController()

    def _stop(self, reason=""):
        self.state.follow_active = False
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.timeout = reason == "timeout_stop"
        if reason:
            self.state.last_error = reason

    def _apply_follow(self, command, now_ms):
        """执行一条跟随控制报文

        @brief 当前最小主线按 `seq` 去重, `valid=0` 进入保持
        @param command 已解析的跟随命令
        @param now_ms 当前毫秒时间
        @return str
        """

        if int(command.seq) <= int(self.state.last_seq):
            return "IGNORED"
        self.safety.mark_command(now_ms)
        self.safety.clear_estop()
        self.state.last_error = ""
        self.state.timeout = False
        self.state.last_seq = int(command.seq)
        if not command.valid:
            self.state.follow_active = False
            self.state.velocity_command = (0.0, 0.0, 0.0)
            return "HOLD"
        self.state.follow_active = True
        world_dx, world_dy = rotate_body_delta_to_world(
            command.dx,
            command.dy,
            self.state.heading_deg,
        )
        self.state.odom[0] += world_dx
        self.state.odom[1] += world_dy
        self.state.heading_deg += command.dtheta
        self.state.velocity_command = (
            command.dx,
            command.dy,
            self.heading_controller.compute(command.dtheta),
        )
        return "BUSY"

    def apply_command(self, command, now_ms):
        """执行一条协议命令

        @brief 维持最小 arm/busy/odom/heading 状态
        @param command 已解析命令
        @param now_ms 当前毫秒时间
        @return str
        """

        if command.kind == "ping":
            return "ACK"
        if command.kind == "state_query":
            return render_state(self.state)
        if command.kind == "follow":
            return self._apply_follow(command, now_ms)

        self.safety.mark_command(now_ms)
        self.state.last_error = ""
        self.state.timeout = False

        if command.kind == "arm":
            return "ACK"
        if command.kind == "disarm":
            self._stop()
            return "ACK"
        if command.kind == "stop":
            self.safety.trigger_estop()
            self._stop("estop")
            return "DONE"
        if command.kind == "reset_odom":
            self.state.odom[0] = 0.0
            self.state.odom[1] = 0.0
            self.state.heading_deg = 0.0
            self.state.last_seq = 0
            self.state.timeout = False
            self.safety.clear_estop()
            return "ACK"
        if command.kind == "hold":
            self.state.follow_active = False
            self.state.velocity_command = (0.0, 0.0, 0.0)
            self.safety.clear_estop()
            return "DONE"

        self.safety.clear_estop()

        if command.kind == "vel":
            self.state.follow_active = True
            self.state.velocity_command = (command.vx, command.vy, command.omega)
            return "BUSY"

        if command.kind == "move":
            self.state.follow_active = True
            world_dx, world_dy = rotate_body_delta_to_world(
                command.dx,
                command.dy,
                self.state.heading_deg,
            )
            self.state.odom[0] += world_dx
            self.state.odom[1] += world_dy
            self.state.heading_deg += command.dtheta
            self.state.velocity_command = (
                command.dx,
                command.dy,
                self.heading_controller.compute(command.dtheta),
            )
            return "BUSY"

        self.state.last_error = "unsupported_command"
        return "ERR"

    def tick(self, now_ms):
        """推进最小执行循环

        @brief 当前只负责安全停机收口
        @param now_ms 当前毫秒时间
        @return str
        """

        if self.safety.should_stop(now_ms):
            reason = "estop" if self.safety.estop_active else "timeout_stop"
            self._stop(reason)
            return "DONE"
        if self.state.follow_active:
            return "BUSY"
        return "ACK"

    def state_line(self):
        """返回状态回包文本

        @brief 对外暴露最小 `STATE` 文本
        @return str
        """

        return render_state(self.state)
