"""辅车运行时执行闭环

@file src/assistant/motion_runtime.py
"""

from config.params import FOLLOW_TIMEOUT_MS
from assistant.protocol import Command
from assistant.safety import SafetyGuard
from assistant.status import AssistantState, render_state


class MotionRuntime:
    """负责执行辅车命令并维护运行时状态

    @brief 管理协议命令、状态更新和安全停机
    """

    def __init__(self, timeout_ms=FOLLOW_TIMEOUT_MS):
        # 运行时状态集中保存在一个对象中, 便于执行层和回包层复用
        self.state = AssistantState()

        # 安全保护负责管理急停和命令超时
        self.safety = SafetyGuard(timeout_ms=timeout_ms)

    def _stop(self, reason=""):
        """将辅车状态收口为停止

        @brief 清空运动输出并记录停机原因
        @param reason 停机原因
        """

        self.state.follow_active = False
        self.state.state_label = "TIMEOUT" if reason == "timeout_stop" else "IDLE"
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.timeout = reason == "timeout_stop"
        if reason:
            self.state.last_error = reason

    def _preserve_timeout_stop(self):
        """在超时锁定下执行停止动作但保留超时对外状态

        @brief 供超时后的普通辅助入口复用
        """

        self.state.follow_active = False
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.state_label = "TIMEOUT"
        self.state.timeout = True
        self.state.last_error = "timeout_stop"

    def _is_timeout_locked(self):
        """判断当前是否处于超时锁定状态

        @brief 超时后仅允许新序号跟随或显式复位退出
        @return bool
        """

        return bool(self.state.timeout) or self.state.state_label == "TIMEOUT"

    def _clear_follow_deadline(self):
        """清除跟随链路的超时基准

        @brief 辅助入口结束或打断跟随后, 后续 tick 不应再重放旧超时
        """

        self.safety.last_command_ms = None

    def _reject_unsupported_command(self):
        """拒绝当前阶段不支持的入口

        @brief 保持当前运动输出不变, 仅对外返回错误结果
        @return str
        """

        if not self._is_timeout_locked():
            self.state.timeout = False
        self.state.last_error = "unsupported_command"
        return "ERR"

    def _apply_follow(self, command, now_ms):
        """执行一条跟随控制报文

        @brief 按序号去重并将跟随控制写入辅车状态
        @param command 已解析的跟随命令
        @param now_ms 当前毫秒时间
        @return str
        """

        # 序号未前进时直接忽略, 避免重复报文覆盖当前状态
        if int(command.seq) <= int(self.state.last_seq):
            return "IGNORED"

        self.safety.mark_command(now_ms)
        self.safety.clear_estop()
        self.state.last_error = ""
        self.state.timeout = False
        self.state.last_seq = int(command.seq)

        # `valid=0` 表示当前控制拍没有有效目标, 运行时进入保持状态
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
        """执行一条协议命令

        @brief 根据命令类型更新辅车状态并返回执行结果
        @param command 已解析命令
        @param now_ms 当前毫秒时间
        @return str
        """

        # 查询类命令不修改安全状态, 直接返回当前结果
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
        """推进辅车执行循环

        @brief 根据急停和超时状态决定是否停机
        @param now_ms 当前毫秒时间
        @return str
        """

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
        """返回状态回包文本

        @brief 按协议格式输出当前状态文本
        @return str
        """

        return render_state(self.state)
