"""最小常驻运行时 owner."""

from diagnostics.manager import build_uart3_logger_manager
from hardware.uart_bus import create_uart3, create_uart6


class RuntimeCore:
    """持有系统最小常驻状态和日志入口."""

    def __init__(
        self,
        vehicle_role,
        now_ms,
        now_us,
        create_uart3_func=create_uart3,
        create_uart6_func=create_uart6,
        logger_builder=build_uart3_logger_manager,
    ) -> None:
        self.vehicle_role = str(vehicle_role)
        self.now_ms = now_ms
        self.now_us = now_us
        self.uart3 = create_uart3_func()
        self.uart6 = create_uart6_func()
        self.error_count = 0
        self.last_error_stage = None
        self._last_error_log_text = None
        self.oom_count = 0
        self.last_oom_stage = None
        self.logger_manager = logger_builder(self.uart3, oom_callback=self.record_oom)
        self.log_system = self.logger_manager.get_logger("system.boot")
        self.log_command = self.logger_manager.get_logger("services.command")
        self.log_vision = self.logger_manager.get_logger("vision.state")
        self.log_health = self.logger_manager.get_logger("system.health")
        self.pit_flag = False
        self.tick_count = 0
        self.ticker = None
        self.boot_time_ms = int(now_ms())
        self.last_time_us = int(now_us())
        self.last_loop_dt_us = 0
        self.max_loop_dt_us = 0
        self.loop_dt_total_us = 0
        self.loop_overrun_count = 0
        self.last_exception_text = "none"

    def record_oom(self, stage: str) -> None:
        """记录一次轻量 OOM 观测信号."""
        self.oom_count = int(self.oom_count) + 1
        self.last_oom_stage = str(stage)
