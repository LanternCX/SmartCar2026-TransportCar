"""底盘平面运动与航向规划."""

import math

from config.params import (
    AUTO_OMEGA_MAX,
    HOLD_SPEED_EPS,
    POS_KP,
    POS_MAX_SPEED,
    YAW_KD,
)
from control.pid_math import clamp


def _normalize_angle(angle_deg):
    """把角度规约到 [-180, 180)."""
    while angle_deg >= 180.0:
        angle_deg -= 360.0
    while angle_deg < -180.0:
        angle_deg += 360.0
    return angle_deg


class MotionPlanner:
    """封装航向控制和位置/速度模式规划公式."""

    def __init__(self, kinematics):
        self.kinematics = kinematics

    def compute_angle_error_deg(self, target_angle, current_angle):
        """计算最短路径角差."""
        return _normalize_angle(float(target_angle) - float(current_angle))

    def resolve_continuous_heading_target(self, target_angle, current_angle):
        """将目标角映射到当前连续航向附近."""
        return float(current_angle) + self.compute_angle_error_deg(
            target_angle, current_angle
        )

    def compute_omega_cmd(self, state, dt_s, cmd_angle, cmd_omega):
        """根据角度或角速度命令计算角速度输出."""
        if cmd_angle is not None:
            state.heading_target = self.resolve_continuous_heading_target(
                cmd_angle, state.heading_est
            )
            omega_pid = state.yaw_pid.update(
                state.heading_target, state.heading_est, dt_s
            )
            omega_auto = omega_pid - YAW_KD * state.yaw_rate
            omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)
        elif cmd_omega is not None:
            omega_cmd = cmd_omega
            if abs(omega_cmd) < HOLD_SPEED_EPS:
                omega_pid = state.yaw_pid.update(
                    state.heading_target, state.heading_est, dt_s
                )
                omega_auto = omega_pid - YAW_KD * state.yaw_rate
                omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)
            else:
                state.heading_target = state.heading_est
                state.yaw_pid.reset()
                state.yaw_integral = 0.0
        else:
            omega_pid = state.yaw_pid.update(
                state.heading_target, state.heading_est, dt_s
            )
            omega_auto = omega_pid - YAW_KD * state.yaw_rate
            omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)

        if hasattr(state.yaw_pid, "integral"):
            state.yaw_integral = state.yaw_pid.integral

        return omega_cmd

    def compute_planar_targets(
        self,
        dt_s,
        heading_est_deg,
        odometry,
        last_cmd,
        active_target_x,
        active_target_y,
    ):
        """计算平面目标速度, 保持位置模式与速度模式语义不变."""
        if active_target_x is not None or active_target_y is not None:
            target_x = active_target_x if active_target_x is not None else 0.0
            target_y = active_target_y if active_target_y is not None else 0.0

            err_x = target_x - odometry.x
            err_y = target_y - odometry.y
            v_world_x = err_x * POS_KP
            v_world_y = err_y * POS_KP

            v_speed = math.sqrt(v_world_x * v_world_x + v_world_y * v_world_y)
            if v_speed > POS_MAX_SPEED:
                scale = POS_MAX_SPEED / v_speed
                v_world_x *= scale
                v_world_y *= scale

            theta_rad = math.radians(heading_est_deg)
            cos_t = math.cos(theta_rad)
            sin_t = math.sin(theta_rad)
            vx_rob_ctrl = v_world_x * cos_t + v_world_y * sin_t
            vy_rob_ctrl = -v_world_x * sin_t + v_world_y * cos_t

            vx_pulses = self.kinematics.velocity_m_s_to_pulses(vx_rob_ctrl, dt_s)
            vy_pulses = self.kinematics.velocity_m_s_to_pulses(vy_rob_ctrl, dt_s)
            return vx_pulses * 3.0, vy_pulses * 3.0

        return float(last_cmd.get("vx", 0.0)), float(last_cmd.get("vy", 0.0))
