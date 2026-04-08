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
        """把编码器脉冲数换算成轮缘位移.

        @brief 统一三轮底盘里程换算口径, 避免状态层重复拼公式。
        """

        return float(pulses) * self.m_per_pulse

    def velocity_pulses_to_m_s(self, pulse_speed, dt_s):
        """把单拍脉冲增量换算成线速度.

        @brief 给里程计和速度环共用编码器到米每秒的换算入口。
        """

        return self.pulses_to_m(pulse_speed) / float(dt_s)

    def forward_kinematics(self, vm, vl, vr):
        """把三轮线速度解算为车体系速度.

        @brief 给辅车里程累计和跟随控制提供统一前向运动学结果。
        """

        vx = (0.5 * (float(vl) + float(vr))) - float(vm)
        vy = (math.sqrt(3.0) * 0.5) * (float(vl) - float(vr))
        omega = float(vl) + float(vr) + float(vm)
        return (vx, vy, omega)

    def inverse_kinematics(self, vx, vy, omega):
        """把车体系目标速度分解为三轮目标速度.

        @brief 给速度环输出每个轮位应追踪的目标值。
        """

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
        """把车体系速度积分到世界坐标.

        @brief 让辅车跟随逻辑直接基于累计位姿误差工作。
        """

        cos_heading = math.cos(float(heading_rad))
        sin_heading = math.sin(float(heading_rad))
        world_x = (float(vx_robot) * cos_heading) - (float(vy_robot) * sin_heading)
        world_y = (float(vx_robot) * sin_heading) + (float(vy_robot) * cos_heading)
        self.x += world_x * float(dt_s)
        self.y += world_y * float(dt_s)
        return (self.x, self.y)


def build_planar_target(dx, dy):
    """构造世界坐标系下的平面目标.

    @brief 把外部给出的二维目标统一整理成控制层使用的字典结构。
    """

    return {"dx": float(dx), "dy": float(dy)}


def rotate_body_delta_to_world(dx, dy, heading_deg):
    """把车体系位移增量旋转到世界坐标系.

    @brief 用当前航向把跟随目标从车体系转换为里程坐标。
    """

    theta = math.radians(float(heading_deg))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    world_x = float(dx) * cos_t + float(dy) * sin_t
    world_y = -float(dx) * sin_t + float(dy) * cos_t
    return (world_x, world_y)


def inverse_kinematics(dx, dy, omega):
    """提供面向外层调用的逆运动学捷径.

    @brief 复用统一底盘模型, 避免外部直接依赖类实例构造。
    """

    return build_kinematics().inverse_kinematics(float(dx), float(dy), float(omega))


def build_kinematics():
    """创建辅车底盘运动学模型.

    @brief 把三轮底盘几何参数集中收口在同一个入口。
    """

    return OmniKinematics()


def build_odometry():
    """创建辅车里程累计对象.

    @brief 创建供运行时持有的累计位姿对象。
    """

    return Odometry()


def update_odometry_from_wheels(state, heading_deg=None):
    """根据当前轮速刷新辅车累计里程.

    @brief 根据轮速和航向把本拍位移积分到世界坐标系。
    """

    vm = state.kinematics.velocity_pulses_to_m_s(state.wheel_speeds["m"], state.tick_s)
    vl = state.kinematics.velocity_pulses_to_m_s(state.wheel_speeds["l"], state.tick_s)
    vr = state.kinematics.velocity_pulses_to_m_s(state.wheel_speeds["r"], state.tick_s)
    vx_robot, vy_robot, _ = state.kinematics.forward_kinematics(vm, vl, vr)
    odom_x, odom_y = state.odometry.update(
        vx_robot,
        vy_robot,
        math.radians(float(state.heading_deg if heading_deg is None else heading_deg)),
        state.tick_s,
    )
    state.odom[0] = odom_x
    state.odom[1] = odom_y
    return (odom_x, odom_y)


def scale_wheel_targets(wheel_targets, limit):
    """按统一比例缩放三轮目标.

    @brief 当任一轮超过上限时, 让三轮一起按同一比例缩放。
    """

    limit = abs(float(limit))
    prepared = {
        "m": float(wheel_targets.get("m", 0.0)),
        "l": float(wheel_targets.get("l", 0.0)),
        "r": float(wheel_targets.get("r", 0.0)),
    }
    max_speed = max(abs(prepared["m"]), abs(prepared["l"]), abs(prepared["r"]))
    if max_speed <= limit or max_speed <= 0.0:
        return prepared
    scale = limit / max_speed
    return {
        "m": prepared["m"] * scale,
        "l": prepared["l"] * scale,
        "r": prepared["r"] * scale,
    }


def resolve_follow_velocity(state):
    """按当前跟随目标解算车体系平移速度.

    @brief 根据世界系位置误差生成受限的车体系平移指令。
    """

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
