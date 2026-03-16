"""@brief 运行时诊断 facade.

@note facade 仅只读聚合 owner 状态, 不缓存第二份运行时状态
"""

from services.runtime.diag_health import (
    build_health_query_response,
    build_health_snapshot,
    build_tick_query_response,
    build_tick_snapshot,
)
from services.runtime.diag_format import (
    HEALTH_SNAPSHOT_FIELDS,
    TICK_SNAPSHOT_FIELDS,
    VISION_SNAPSHOT_FIELDS,
)
from services.runtime.diag_motion import (
    build_encoder_snapshot,
    build_imu_snapshot,
    build_lock_snapshot,
    build_log_snapshot,
    build_motor_snapshot,
    build_pos_snapshot,
)
from services.runtime.diag_vision import (
    build_vision_query_response,
    build_vision_snapshot,
)


class DiagnosticsFacade:
    """@brief 统一聚合 query 所需的运行时诊断数据."""

    def __init__(self, runtime) -> None:
        self._runtime = runtime

    def _now_ms(self) -> int:
        """@brief 返回当前毫秒时间."""
        return int(self._runtime.now_ms())

    def _get_vision_runtime(self):
        """@brief 返回视觉运行时 owner, 若未启用则返回 None."""
        return getattr(self._runtime, "vision_runtime", None)

    def _get_vision_state_name(self) -> str:
        """@brief 返回当前视觉状态名."""
        coordinator = getattr(self._runtime, "vision_coordinator", None)
        if coordinator is None:
            return "UNKNOWN"
        if hasattr(coordinator, "get_state_name"):
            return coordinator.get_state_name()
        return str(getattr(coordinator, "state_name", "UNKNOWN"))

    def _get_rear_only_mode(self) -> bool:
        """@brief 返回当前后轮模式标记."""
        vision_runtime = self._get_vision_runtime()
        if vision_runtime is not None:
            resolved_target = getattr(vision_runtime, "resolved_target", None)
            if resolved_target is not None:
                return bool(resolved_target.rear_only_mode)
        coordinator = getattr(self._runtime, "vision_coordinator", None)
        if coordinator is not None:
            resolved_target = getattr(coordinator, "resolved_target", None)
            if resolved_target is not None:
                return bool(resolved_target.rear_only_mode)
        return bool(self._runtime.command_session.rear_only_mode)

    def _get_command_lock(self) -> bool:
        """@brief 返回命令锁状态."""
        return bool(self._runtime.command_session.command_lock)

    def _get_chassis_state(self):
        """@brief 返回底盘状态 owner."""
        return self._runtime.chassis_state

    def build_health_snapshot(self):
        """@brief 返回健康摘要快照."""
        return build_health_snapshot(self)

    def build_health_query_response(self):
        """@brief 直接构造 health 查询响应, 减少中间对象."""
        return build_health_query_response(self)

    def build_tick_snapshot(self):
        """@brief 返回 tick 统计快照."""
        return build_tick_snapshot(self._runtime)

    def build_tick_query_response(self):
        """@brief 直接构造 tick 查询响应, 减少中间对象."""
        return build_tick_query_response(self._runtime)

    def build_imu_snapshot(self):
        """@brief 返回 IMU 摘要快照."""
        return build_imu_snapshot(self._get_chassis_state())

    def build_encoder_snapshot(self):
        """@brief 返回编码器摘要快照."""
        return build_encoder_snapshot(self._get_chassis_state())

    def build_motor_snapshot(self):
        """@brief 返回电机摘要快照."""
        return build_motor_snapshot(
            self._get_chassis_state(),
            self._get_rear_only_mode(),
        )

    def build_vision_snapshot(self):
        """@brief 返回视觉摘要快照."""
        return build_vision_snapshot(self)

    def build_vision_query_response(self):
        """@brief 直接构造 vision 查询响应, 减少中间对象."""
        return build_vision_query_response(self)

    def build_pos_snapshot(self):
        """@brief 返回位置查询快照."""
        return build_pos_snapshot(self._get_chassis_state())

    def build_lock_snapshot(self):
        """@brief 返回锁定状态快照."""
        return build_lock_snapshot(self._get_command_lock())

    def build_log_snapshot(self):
        """@brief 返回日志配置快照."""
        return build_log_snapshot(self._runtime.logger_manager)
