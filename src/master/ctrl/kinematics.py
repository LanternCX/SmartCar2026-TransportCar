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
        """把编码器脉冲数换算成轮周位移.

        @brief 所有速度和里程计算都先经过这层统一比例, 避免外层散落重复常数。
        """

        return float(pulses) * self.m_per_pulse

    def velocity_pulses_to_m_s(self, pulse_speed, dt_s):
        """把单拍脉冲增量换算成线速度.

        @brief 这里依赖当前控制周期时长, 给里程与速度环共享同一套单位转换。
        """

        return self.pulses_to_m(pulse_speed) / float(dt_s)

    def forward_kinematics(self, vm, vl, vr):
        """根据三轮线速度恢复车体速度.

        @brief 输出的是车体坐标系速度, 世界坐标变换留给里程模块处理。
        """

        vx = (0.5 * (float(vl) + float(vr))) - float(vm)
        vy = (math.sqrt(3.0) * 0.5) * (float(vl) - float(vr))
        omega = float(vl) + float(vr) + float(vm)
        return (vx, vy, omega)

    def inverse_kinematics(self, vx, vy, omega):
        """把车体期望速度拆成三轮目标速度.

        @brief 这是速度控制链进入单轮目标前的唯一分配入口。
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
        """把车体速度旋到世界坐标后累计里程.

        @brief 里程对象只负责积分, 不参与目标生成和航向控制。
        """

        cos_heading = math.cos(float(heading_rad))
        sin_heading = math.sin(float(heading_rad))
        world_x = (float(vx_robot) * cos_heading) - (float(vy_robot) * sin_heading)
        world_y = (float(vx_robot) * sin_heading) + (float(vy_robot) * cos_heading)
        self.x += world_x * float(dt_s)
        self.y += world_y * float(dt_s)
        return (self.x, self.y)


def build_planar_target(dx, dy):
    """构造视觉跟随使用的二维平面目标.

    @brief 统一把外部输入整理成控制链约定的 `dx/dy` 结构。
    """

    return {"dx": float(dx), "dy": float(dy)}


def build_kinematics():
    """构造主车运动学对象.

    @brief 由状态装配层持有实例, 避免各流程各自复制几何参数。
    """

    return OmniKinematics()


def build_odometry():
    """构造主车里程累计对象.

    @brief 把跨周期里程积分状态收口到独立对象里。
    """

    return Odometry()


def update_odometry_from_wheels(state):
    """根据当前轮速更新主车里程快照.

    @brief 这个入口把轮速、运动学和里程对象串起来, 给运行时写回统一的 `odom` 输出。
    """

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
