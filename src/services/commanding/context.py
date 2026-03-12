"""命令处理显式上下文."""

from control.pid_math import reset_pi_state


class TransportCommandContext:
    """面向 handler 暴露的受控运行时上下文."""

    def __init__(self, runtime, reply_uart, source: str = "uart6") -> None:
        self._runtime = runtime
        self.session = runtime.command_session
        self.chassis_state = runtime.chassis_state
        self.reply_uart = reply_uart
        self.source = source
        self.uart3 = runtime.uart3
        self.logger_manager = runtime.logger_manager

    def reply(self, text: str) -> None:
        """向当前 query 响应串口写回文本."""
        self.reply_uart.write(text)

    def get_diagnostics_facade(self):
        """返回当前运行时诊断 facade."""
        facade = getattr(self, "_diagnostics_facade", None)
        if facade is None:
            from services.runtime.diagnostics_facade import DiagnosticsFacade

            facade = DiagnosticsFacade(self._runtime)
            self._diagnostics_facade = facade
        return facade

    def finalize_route(self, dispatched) -> None:
        """通过命令会话完成一次路由后的统一收口."""
        state = self.chassis_state
        odometry = state.odometry
        use_velocity_echo = self.session.finalize_route(
            dispatched,
            heading_target=state.heading_target,
            odom_x=odometry.x,
            odom_y=odometry.y,
            heading_est=state.heading_est,
            now_ms=self._runtime.now_ms(),
        )
        if use_velocity_echo:
            vx = self.session.last_cmd.get("vx") or 0.0
            vy = self.session.last_cmd.get("vy") or 0.0
            omega = self.session.last_cmd.get("omega") or 0.0
            self._runtime.inverse_kinematics(vx, vy, omega)

    def reset_runtime(self) -> None:
        """复位运行时与命令会话状态."""
        state = self.chassis_state
        state.odometry.reset()
        state.heading_est = 0.0
        state.heading_target = 0.0
        state.yaw_pid.reset()
        state.yaw_integral = 0.0
        state.q_est.w = 1.0
        state.q_est.x = 0.0
        state.q_est.y = 0.0
        state.q_est.z = 0.0
        state.last_yaw_rad = 0.0
        state.gyro_lpf.reset(0.0)
        reset_pi_state(state.wheel_states)
        self.session.reset_runtime_state()
        self._runtime.vision_coordinator.clear_runtime()
