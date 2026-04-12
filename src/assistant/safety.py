"""位于辅车运行时与电机控制之间, 统一判断主车命令超时和急停是否应抢占当前动作。

它对外只提供停机判定与安全状态维护, 供主链在每轮推进前先完成安全收口。

@file src/assistant/safety.py
"""


class SafetyGuard:
    """辅车安全保护器

    @brief 管理急停状态和命令超时停机
    """

    def __init__(self, timeout_ms):
        # 超时阈值和最近命令时间由安全保护统一维护
        self.timeout_ms = int(timeout_ms)
        # 最近一次收到主车命令的时间, 用来判断链路是否超时
        self.last_command_ms = None
        # 急停一旦触发就优先于普通超时检查
        self.estop_active = False

    def mark_command(self, now_ms):
        """记录最近命令时间

        @brief 新命令到达时刷新超时检查基准
        @param now_ms 当前毫秒时间
        """

        self.last_command_ms = int(now_ms)

    def trigger_estop(self):
        """触发急停

        @brief 将安全状态锁定为停机
        """

        self.estop_active = True

    def clear_estop(self):
        """清除急停

        @brief 恢复普通超时检查流程
        """

        self.estop_active = False

    def should_stop(self, now_ms):
        """判断是否应停机

        @brief 急停优先, 其次检查命令是否超时
        @param now_ms 当前毫秒时间
        @return bool
        """

        if self.estop_active:
            return True
        if self.last_command_ms is None:
            return False
        return int(now_ms) - self.last_command_ms >= self.timeout_ms
