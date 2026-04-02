"""主车运动学边界.

@file src/master/ctrl/kinematics.py
"""

import math


class OmniKinematics:
    """封装三轮底盘的单位换算与前逆运动学."""

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
