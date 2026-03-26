"""辅车最小安全保护

@file src/assistant/safety.py
"""


class SafetyGuard:
    """辅车安全保护器

    @brief 管理超时停机与急停状态
    """

    def __init__(self, timeout_ms):
        self.timeout_ms = int(timeout_ms)
        self.last_command_ms = None
        self.estop_active = False

    def mark_command(self, now_ms):
        """记录最近命令时间

        @brief 新命令到达时刷新看门狗
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

        @brief 允许系统恢复到普通看门狗检查
        """

        self.estop_active = False

    def should_stop(self, now_ms):
        """判断是否应停机

        @brief 急停优先, 其次检查命令超时
        @param now_ms 当前毫秒时间
        @return bool
        """

        if self.estop_active:
            return True
        if self.last_command_ms is None:
            return False
        return int(now_ms) - self.last_command_ms >= self.timeout_ms
