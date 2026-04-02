"""辅车运动学边界.

@file src/assistant/ctrl/kinematics.py
"""

import math


class OmniKinematics:
    """封装三轮底盘的位移换算与前逆运动学."""

    def __init__(self):
        self.wheel_diameter = 0.060
        self.gear_ratio = 30.0
        self.encoder_ppr = 7.0
        self.counts_per_rev = self.encoder_ppr * self.gear_ratio * 4.0
        self.m_per_pulse = (self.wheel_diameter * math.pi) / self.counts_per_rev

    def pulses_to_m(self, pulses):
        return float(pulses) * self.m_per_pulse

    def velocity_pulses_to_m_s(self, pulse_speed, dt_s):
        return self.pulses_to_m(pulse_speed) / float(dt_s)

    def forward_kinematics(self, vm, vl, vr):
        vx = (0.5 * (float(vl) + float(vr))) - float(vm)
        vy = (math.sqrt(3.0) * 0.5) * (float(vl) - float(vr))
        omega = float(vl) + float(vr) + float(vm)
        return (vx, vy, omega)

    def inverse_kinematics(self, vx, vy, omega):
        inv_3 = 1.0 / 3.0
        sqrt3_3 = math.sqrt(3.0) * inv_3
        return {
            "m": (-2.0 * inv_3 * float(vx)) + (float(omega) * inv_3),
            "l": (float(vx) * inv_3) + (sqrt3_3 * float(vy)) + (float(omega) * inv_3),
            "r": (float(vx) * inv_3) - (sqrt3_3 * float(vy)) + (float(omega) * inv_3),
        }


class Odometry:
    """保存跨周期累计里程."""

    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def update(self, vx_robot, vy_robot, heading_rad, dt_s):
        cos_heading = math.cos(float(heading_rad))
        sin_heading = math.sin(float(heading_rad))
        world_x = (float(vx_robot) * cos_heading) - (float(vy_robot) * sin_heading)
        world_y = (float(vx_robot) * sin_heading) + (float(vy_robot) * cos_heading)
        self.x += world_x * float(dt_s)
        self.y += world_y * float(dt_s)
        return (self.x, self.y)


def build_planar_target(dx, dy):
    return {"dx": float(dx), "dy": float(dy)}


def rotate_body_delta_to_world(dx, dy, heading_deg):
    theta = math.radians(float(heading_deg))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    world_x = float(dx) * cos_t + float(dy) * sin_t
    world_y = -float(dx) * sin_t + float(dy) * cos_t
    return (world_x, world_y)


def inverse_kinematics(dx, dy, omega):
    return build_kinematics().inverse_kinematics(float(dy), float(dx), float(omega))


def build_kinematics():
    return OmniKinematics()


def build_odometry():
    return Odometry()


def update_odometry_from_wheels(state):
    vm = state.kinematics.velocity_pulses_to_m_s(state.wheel_speeds["m"], state.tick_s)
    vl = state.kinematics.velocity_pulses_to_m_s(state.wheel_speeds["l"], state.tick_s)
    vr = state.kinematics.velocity_pulses_to_m_s(state.wheel_speeds["r"], state.tick_s)
    vx_robot, vy_robot, _ = state.kinematics.forward_kinematics(vm, vl, vr)
    odom_x, odom_y = state.odometry.update(
        vx_robot,
        vy_robot,
        math.radians(float(state.heading_deg)),
        state.tick_s,
    )
    state.odom[0] = odom_x
    state.odom[1] = odom_y
    return (odom_x, odom_y)


def resolve_follow_velocity(state):
    if state.follow_target_world is None:
        return (0.0, 0.0)
    err_world_x = float(state.follow_target_world[0]) - float(state.odom[0])
    err_world_y = float(state.follow_target_world[1]) - float(state.odom[1])
    v_world_x = err_world_x * state.follow_position_kp
    v_world_y = err_world_y * state.follow_position_kp
    speed = math.sqrt((v_world_x * v_world_x) + (v_world_y * v_world_y))
    if speed > state.follow_position_max_speed and speed > 0.0:
        scale = state.follow_position_max_speed / speed
        v_world_x *= scale
        v_world_y *= scale
    theta_rad = math.radians(float(state.heading_deg))
    cos_t = math.cos(theta_rad)
    sin_t = math.sin(theta_rad)
    body_dx = (v_world_x * cos_t) - (v_world_y * sin_t)
    body_dy = (v_world_x * sin_t) + (v_world_y * cos_t)
    return (body_dx, body_dy)
