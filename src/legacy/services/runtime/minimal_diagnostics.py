"""最小诊断 owner 组装器."""

from services.runtime.diagnostics_facade import DiagnosticsFacade


class _RuntimeOwnerView:
    """将多个 owner 暴露为诊断 facade 所需的最小公共接口."""

    def __init__(self, core, command_owner, motion_owner, vision_owner) -> None:
        self._core = core
        self._command_owner = command_owner
        self._motion_owner = motion_owner
        self._vision_owner = vision_owner

    def now_ms(self):
        """返回当前毫秒时间."""
        return self._core.now_ms()

    @property
    def boot_time_ms(self):
        """返回启动时间戳."""
        return self._core.boot_time_ms

    @property
    def oom_count(self):
        """返回 OOM 计数."""
        return self._core.oom_count

    @property
    def last_oom_stage(self):
        """返回最近一次 OOM 阶段."""
        return self._core.last_oom_stage

    @property
    def last_exception_text(self):
        """返回最近异常文本."""
        return self._core.last_exception_text

    @property
    def tick_count(self):
        """返回 tick 计数."""
        return self._core.tick_count

    @property
    def last_loop_dt_us(self):
        """返回上一拍耗时."""
        return self._core.last_loop_dt_us

    @property
    def max_loop_dt_us(self):
        """返回最大拍耗时."""
        return self._core.max_loop_dt_us

    @property
    def loop_dt_total_us(self):
        """返回累计拍耗时."""
        return self._core.loop_dt_total_us

    @property
    def loop_overrun_count(self):
        """返回超时次数."""
        return self._core.loop_overrun_count

    @property
    def logger_manager(self):
        """返回日志配置 owner."""
        return self._core.logger_manager

    @property
    def command_session(self):
        """返回命令会话 owner."""
        return self._command_owner.command_session

    @property
    def chassis_state(self):
        """返回底盘状态 owner."""
        return self._motion_owner.chassis_state

    @property
    def vision_runtime(self):
        """返回视觉运行时 owner."""
        return getattr(self._vision_owner, "vision_runtime", None)

    @property
    def vision_coordinator(self):
        """返回视觉协调器 owner."""
        return getattr(self._vision_owner, "vision_coordinator", None)


class MinimalDiagnostics(DiagnosticsFacade):
    """基于显式 owner 构造最小诊断 facade."""

    def __init__(self, core, command_owner, motion_owner, vision_owner) -> None:
        runtime_view = _RuntimeOwnerView(
            core=core,
            command_owner=command_owner,
            motion_owner=motion_owner,
            vision_owner=vision_owner,
        )
        super().__init__(runtime_view)
        self._core = core
        self._command_owner = command_owner
        self._motion_owner = motion_owner
        self._vision_owner = vision_owner
