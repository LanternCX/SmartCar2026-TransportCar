"""运行时诊断 facade."""


class DiagnosticsFacade:
    """统一聚合 query 所需的运行时诊断数据."""

    def __init__(self, runtime) -> None:
        self._runtime = runtime

    def _now_ms(self) -> int:
        return int(self._runtime.now_ms())

    def _get_rear_only_mode(self) -> bool:
        coordinator = getattr(self._runtime, "vision_coordinator", None)
        if coordinator is not None:
            resolved_target = getattr(coordinator, "resolved_target", None)
            if resolved_target is not None:
                return bool(resolved_target.rear_only_mode)
        return bool(self._runtime.command_session.rear_only_mode)

    def _get_command_lock(self) -> bool:
        return bool(self._runtime.command_session.command_lock)

    def _get_chassis_state(self):
        return self._runtime.chassis_state

    def build_health_snapshot(self):
        """返回健康摘要快照."""
        return {
            "alive": 1,
            "uptime_ms": max(0, self._now_ms() - int(self._runtime.boot_time_ms)),
            "lock": 1 if self._get_command_lock() else 0,
            "rear": 1 if self._get_rear_only_mode() else 0,
            "last_err": self._runtime.last_exception_text,
            "vision_state": self.build_vision_snapshot()["state"],
        }

    def build_tick_snapshot(self):
        """返回 tick 统计快照."""
        avg_us = 0
        if self._runtime.tick_count > 0:
            avg_us = int(self._runtime.loop_dt_total_us / self._runtime.tick_count)
        return {
            "count": int(self._runtime.tick_count),
            "last_us": int(self._runtime.last_loop_dt_us),
            "max_us": int(self._runtime.max_loop_dt_us),
            "avg_us": avg_us,
            "overrun": int(self._runtime.loop_overrun_count),
        }

    def build_imu_snapshot(self):
        """返回 IMU 摘要快照."""
        chassis_state = self._get_chassis_state()
        yaw_rate = 0.0
        gz_raw = 0.0
        heading_est = 0.0
        imu_data = None
        if chassis_state is not None:
            yaw_rate = float(getattr(chassis_state, "yaw_rate", 0.0) or 0.0)
            gz_raw = float(getattr(chassis_state, "last_gz_raw", 0.0) or 0.0)
            heading_est = float(getattr(chassis_state, "heading_est", 0.0) or 0.0)
            imu_data = getattr(chassis_state, "imu_data", None)
        return {
            "ok": 1 if imu_data else 0,
            "yaw_deg": heading_est,
            "yaw_rate_dps": yaw_rate,
            "gz_raw": gz_raw,
        }

    def build_encoder_snapshot(self):
        """返回编码器摘要快照."""
        snapshot = {}
        chassis_state = self._get_chassis_state()
        wheel_states = (
            [] if chassis_state is None else (chassis_state.wheel_states or [])
        )
        for state in wheel_states:
            name = state["name"]
            snapshot["%s_raw" % name] = float(state.get("raw_speed", 0.0))
            snapshot["%s_filt" % name] = float(state.get("filtered_speed", 0.0))
        return snapshot

    def build_motor_snapshot(self):
        """返回电机摘要快照."""
        snapshot = {}
        chassis_state = self._get_chassis_state()
        target_speeds = (
            {} if chassis_state is None else (chassis_state.target_speeds or {})
        )
        wheel_states = (
            [] if chassis_state is None else (chassis_state.wheel_states or [])
        )
        for state in wheel_states:
            name = state["name"]
            snapshot["%s_target" % name] = float(target_speeds.get(name, 0.0) or 0.0)
            snapshot["%s_duty" % name] = float(state.get("duty", 0.0))
        snapshot["rear"] = 1 if self._get_rear_only_mode() else 0
        return snapshot

    def build_vision_snapshot(self):
        """返回视觉摘要快照."""
        coordinator = getattr(self._runtime, "vision_coordinator", None)
        if coordinator is None:
            return {
                "state": "UNKNOWN",
                "obs_age_ms": None,
                "obs_left": None,
                "obs_top": None,
                "obs_right": None,
                "obs_bottom": None,
                "obs_center_x": None,
                "obs_center_y": None,
                "target_x": None,
                "target_y": None,
                "target_angle": None,
            }
        return coordinator.build_snapshot(self._now_ms())

    def build_pos_snapshot(self):
        """返回位置查询快照."""
        chassis_state = self._get_chassis_state()
        odometry = getattr(chassis_state, "odometry", None)
        heading_est = float(getattr(chassis_state, "heading_est", 0.0) or 0.0)
        return {
            "x": float(0.0 if odometry is None else odometry.x),
            "y": float(0.0 if odometry is None else odometry.y),
            "heading_deg": heading_est,
        }

    def build_lock_snapshot(self):
        """返回锁定状态快照."""
        return {"locked": 1 if self._get_command_lock() else 0}

    def build_log_snapshot(self):
        """返回日志配置快照."""
        logger_manager = self._runtime.logger_manager
        modules_text = "none"
        if logger_manager.filter_modules:
            modules_text = "|".join(logger_manager.filter_modules)
        return {
            "profile": logger_manager.profile_name.lower(),
            "level": logger_manager.level_name.lower(),
            "filter": logger_manager.filter_mode,
            "color": 1 if logger_manager.color_enabled else 0,
            "modules": modules_text,
        }
