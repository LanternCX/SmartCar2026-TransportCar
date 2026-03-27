"""辅车运行时执行闭环

@file src/assistant/motion_runtime.py
"""

from config.params import FOLLOW_TIMEOUT_MS
from assistant.protocol import Command
from assistant.safety import SafetyGuard
from assistant.status import AssistantState, render_state
from assistant.stability.control import HeadingController
from assistant.stability.kinematics import rotate_body_delta_to_world


class MotionRuntime:
    """负责执行辅车命令并维护运行时状态

    @brief 管理协议命令、状态更新和安全停机
    """

    def __init__(self, timeout_ms=FOLLOW_TIMEOUT_MS):
        # 运行时状态集中保存在一个对象中, 便于执行层和回包层复用
        self.state = AssistantState()

        # 安全保护负责管理急停和命令超时
        self.safety = SafetyGuard(timeout_ms=timeout_ms)

        # 角度误差统一通过偏航控制器换算为角速度命令
        self.heading_controller = HeadingController()

    def _stop(self, reason=""):
        """将辅车状态收口为停止

        @brief 清空运动输出并记录停机原因
        @param reason 停机原因
        """

        self.state.follow_active = False
        self.state.velocity_command = (0.0, 0.0, 0.0)
        self.state.timeout = reason == "timeout_stop"
        if reason:
            self.state.last_error = reason

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
            self.state.velocity_command = (0.0, 0.0, 0.0)
            return "HOLD"

        self.state.follow_active = True

        # 位移增量先从车体系旋转到世界系, 再累计到里程状态
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

        # 其余控制命令都会刷新看门狗并清空上次错误信息
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

            # 位移命令与跟随命令共用同一套里程和朝向更新逻辑
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
        """推进辅车执行循环

        @brief 根据急停和超时状态决定是否停机
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

        @brief 按协议格式输出当前状态文本
        @return str
        """

        return render_state(self.state)
