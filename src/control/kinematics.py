"""@file kinematics.py
@brief 全向轮运动学与里程计模块

实现三轮全向轮配置下的运动学模型(前/逆向)及单位转换,
以及里程计用于追踪世界坐标系下的位置
"""
import math

from config import motion as motion_params


class OmniKinematics:
    """@class OmniKinematics
    @brief 全向轮运动学模型及单位转换

    基于三轮全向轮配置(中间轮沿车体 y 轴, 左右轮呈 120° 布置),
    提供脉冲/米单位转换以及轮速与机器人体坐标系速度的相互转换
    """

    def __init__(self):
        """@brief 初始化运动学参数

        根据硬件参数计算脉冲到米的转换系数, 包括:
        - wheel_diameter: 轮子直径, 单位米
        - gear_ratio: 电机减速比 30: 1
        - encoder_ppr: 编码器每圈脉冲数 7 PPR
        - counts_per_rev: 轮子一圈的编码器计数
        """
        self.wheel_diameter = float(motion_params.WHEEL_DIAMETER_M)
        self.gear_ratio = 30
        self.encoder_ppr = 7
        self.counts_per_rev = self.encoder_ppr * self.gear_ratio
        self.wheel_circumference = self.wheel_diameter * math.pi
        self.m_per_pulse = self.wheel_circumference / self.counts_per_rev

    def pulses_to_m(self, pulses):
        """@brief 将脉冲数转换为米

        @param pulses 脉冲数
        @return 距离(米)
        """
        return pulses * self.m_per_pulse

    def m_to_pulses(self, meters):
        """@brief 将米转换为脉冲数

        @param meters 距离(米)
        @return 脉冲数
        """
        return meters / self.m_per_pulse

    def velocity_pulses_to_m_s(self, pulse_speed, dt_s):
        """@brief 将脉冲速度转换为物理速度

        @param pulse_speed 脉冲速度, 单位为 pulses/dt_s
        @param dt_s 时间增量(秒), 为计算速度的时间基准
        @return 速度(m/s)
        """
        return self.pulses_to_m(pulse_speed) / dt_s

    def velocity_m_s_to_pulses(self, m_s_speed, dt_s):
        """@brief 将物理速度转换为脉冲速度

        @param m_s_speed 速度(m/s)
        @param dt_s 时间增量(秒), 为目标脉冲速度的时间基准
        @return 脉冲速度(pulses/dt_s)
        """
        return self.m_to_pulses(m_s_speed) * dt_s

    def forward_kinematics(self, vm, vl, vr):
        """@brief 前向运动学: 轮速 → 机器人体坐标系速度

        根据三轮速度计算机器人运动速度(x 轴、y 轴、角速度),
        输入输出单位一致(均为脉冲数/时间 或 m/s)

        @details
        配置: 中间轮沿车体 y 轴, 左右轮呈 ±60° 对称布置
        转换公式:
        - vx = 0.5*(vl + vr) - vm
        - vy = (sqrt(3)/2.0)*(vl - vr)
        - omega = vl + vr + vm

        @param vm 中间轮速度, 单位同输出
        @param vl 左轮速度
        @param vr 右轮速度
        @return 元组 (vx, vy, omega), 其中
                - vx: x 轴速度(正向右移)
                - vy: y 轴速度(正向前进)
                - omega: 角速度(正向逆时针)
        """
        vx = 0.5 * (vl + vr) - vm
        vy = (math.sqrt(3) / 2.0) * (vl - vr)
        omega = vl + vr + vm
        return vx, vy, omega

    def inverse_kinematics(self, vx, vy, omega):
        """@brief 逆向运动学: 机器人体坐标系速度 → 轮速

        根据机器人期望运动速度反算各轮目标速度,
        输入输出单位一致

        @details
        反向转换, 求解 vl、vr、vm 使得前向运动学结果为 (vx, vy, omega)

        @param vx x 轴速度
        @param vy y 轴速度
        @param omega 角速度
        @return 元组 (vm, vl, vr), 分别为中间、左、右轮目标速度
        """
        inv_3 = 1.0 / 3.0
        sqrt3_3 = math.sqrt(3) * inv_3

        vl = (vx * inv_3) + (sqrt3_3 * vy) + (omega * inv_3)
        vr = (vx * inv_3) - (sqrt3_3 * vy) + (omega * inv_3)
        vm = (-2.0 * inv_3 * vx) + (omega * inv_3)

        return vm, vl, vr


class Odometry:
    """@class Odometry
    @brief 里程计, 用于追踪世界坐标系下的位置

    积分机器人体坐标系速度并根据朝向角转换到世界坐标系,
    维护当前位置的 x、y 坐标
    """

    def __init__(self, distance_scale=1.0):
        """@brief 初始化里程计状态

        位置初值为原点(0, 0), 可通过 reset() 方法重置
        """
        self.x = 0.0
        self.y = 0.0
        self.distance_scale = float(distance_scale)

    def update(self, vx_robot, vy_robot, theta_rad, dt):
        """@brief 更新位置

        根据机器人体坐标系速度和朝向角, 计算在世界坐标系下的速度分量,
        并积分更新位置

        @details
        变换矩阵:
            [v_world_x]   [cos(theta)  -sin(theta)]   [vx_robot]
            [v_world_y] = [sin(theta)   cos(theta)] * [vy_robot]

        @param vx_robot 机器人坐标系 X 速度 (m/s), 正向右移
        @param vy_robot 机器人坐标系 Y 速度 (m/s), 正向前进
        @param theta_rad 机器人当前朝向 (弧度), 相对世界坐标系
        @param dt 时间间隔 (s)
        """
        cos_t = math.cos(theta_rad)
        sin_t = math.sin(theta_rad)

        v_world_x = vx_robot * cos_t - vy_robot * sin_t
        v_world_y = vx_robot * sin_t + vy_robot * cos_t
        self.x += v_world_x * dt * self.distance_scale
        self.y += v_world_y * dt * self.distance_scale

    def reset(self, x=0.0, y=0.0):
        """@brief 重置里程计

        @param x 新的 X 坐标, 默认为 0.0
        @param y 新的 Y 坐标, 默认为 0.0
        """
        self.x = x
        self.y = y
