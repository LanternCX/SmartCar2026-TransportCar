"""底盘控制主对象."""

import math

from config.params import ANGLE_TOLERANCE, POS_TOLERANCE
from control.pid_math import reset_pi_state
from control.attitude_estimator import AttitudeEstimator
from control.motion_planner import MotionPlanner
from control.wheel_speed_controller import WheelSpeedController


class ChassisController:
    """统一编排轮速、姿态、里程计和控制输出."""

    def __init__(
        self,
        state,
        wheel_speed_controller=None,
        attitude_estimator=None,
        motion_planner=None,
        uart_writer=None,
    ):
        self.state = state
        self.wheel_speed_controller = wheel_speed_controller
        self.attitude_estimator = attitude_estimator
        self.motion_planner = motion_planner
        self.uart_writer = uart_writer

    def tick(
        self,
        dt_s,
        active_target_x,
        active_target_y,
        active_angle,
        cmd_omega,
        active_rear_only_mode,
        last_cmd,
        command_lock,
        rear_only_mode,
    ):
        """执行单拍底盘控制流程."""
        self.update_wheel_speeds()
        self.update_attitude(dt_s)
        omega_cmd = self.compute_omega_cmd(dt_s, active_angle, cmd_omega)
        target_vx_cmd, target_vy_cmd = self.compute_planar_targets(
            dt_s, active_target_x, active_target_y, last_cmd
        )
        self.apply_target_speeds(
            target_vx_cmd,
            target_vy_cmd,
            omega_cmd,
            dt_s,
            active_rear_only_mode,
        )
        return self.check_unlock(last_cmd, command_lock, rear_only_mode)

    def update_wheel_speeds(self):
        """更新轮速滤波状态."""
        controller = self.wheel_speed_controller
        assert controller is not None
        controller.update_wheel_speeds(self.state.wheel_states)

    def update_attitude(self, dt_s):
        """更新姿态和里程计."""
        estimator = self.attitude_estimator
        assert estimator is not None
        estimator.update_attitude(self.state, dt_s)

    def compute_omega_cmd(self, dt_s, cmd_angle, cmd_omega):
        """计算角速度命令."""
        planner = self.motion_planner
        assert planner is not None
        return planner.compute_omega_cmd(self.state, dt_s, cmd_angle, cmd_omega)

    def compute_planar_targets(self, dt_s, active_target_x, active_target_y, last_cmd):
        """计算平面目标速度."""
        planner = self.motion_planner
        assert planner is not None
        return planner.compute_planar_targets(
            dt_s,
            self.state.heading_est,
            self.state.odometry,
            last_cmd,
            active_target_x,
            active_target_y,
        )

    def apply_target_speeds(
        self, target_vx_cmd, target_vy_cmd, omega_cmd, dt_s, active_rear_only_mode
    ):
        """把目标速度分配到三轮速度环."""
        controller = self.wheel_speed_controller
        assert controller is not None
        controller.apply_target_speeds(
            self.state.wheel_states,
            self.state.target_speeds,
            target_vx_cmd,
            target_vy_cmd,
            omega_cmd,
            dt_s,
            active_rear_only_mode,
        )

    def compute_angle_error_deg(self, target_angle, current_angle):
        """复用运动规划器的角差计算."""
        planner = self.motion_planner
        assert planner is not None
        return planner.compute_angle_error_deg(target_angle, current_angle)

    def resolve_continuous_heading_target(self, target_angle, current_angle):
        """复用运动规划器的连续角解析."""
        planner = self.motion_planner
        assert planner is not None
        return planner.resolve_continuous_heading_target(target_angle, current_angle)

    def inverse_kinematics(self, vx, vy, omega):
        """对外暴露逆运动学兼容入口."""
        controller = self.wheel_speed_controller
        assert controller is not None
        return controller.inverse_kinematics(vx, vy, omega)

    def check_unlock(self, last_cmd, command_lock, rear_only_mode):
        """检查锁定是否完成, 保持旧版 auto revert 语义."""
        if not command_lock:
            return command_lock, rear_only_mode, last_cmd

        angle_ok = True
        if last_cmd.get("angle") is not None:
            err_angle = abs(
                self.compute_angle_error_deg(
                    self.state.heading_target, self.state.heading_est
                )
            )
            if err_angle > ANGLE_TOLERANCE:
                angle_ok = False

        pos_ok = True
        if last_cmd.get("x") is not None or last_cmd.get("y") is not None:
            target_x = last_cmd.get("x")
            target_y = last_cmd.get("y")
            x_value = target_x if target_x is not None else 0.0
            y_value = target_y if target_y is not None else 0.0
            ex_val = x_value - self.state.odometry.x
            ey_val = y_value - self.state.odometry.y
            dist_err = math.sqrt(ex_val * ex_val + ey_val * ey_val)
            if dist_err > POS_TOLERANCE:
                pos_ok = False

        if angle_ok and pos_ok:
            command_lock = False
            if rear_only_mode:
                rear_only_mode = False
                if self.uart_writer is not None:
                    self.uart_writer.write(
                        "Target Reached. Auto-revert Rear Mode: False. Stopping.\r\n"
                    )
                last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
                reset_pi_state(self.state.wheel_states)
                self.state.yaw_pid.reset()
                self.state.yaw_integral = 0.0
                self.state.heading_target = self.state.heading_est
                for wheel_state in self.state.wheel_states:
                    wheel_state["motor"].duty(0)
                    wheel_state["duty"] = 0.0

        return command_lock, rear_only_mode, last_cmd
