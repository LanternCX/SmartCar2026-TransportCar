import math


class OmniKinematics:
    """
    全向轮运动学模型及单位转换
    """

    def __init__(self):
        # 轮子直径 (m)
        self.wheel_diameter = 0.060
        # 减速比
        self.gear_ratio = 30
        # 编码器线数 (PPR)
        self.encoder_ppr = 7
        # 4倍频计数 (每圈脉冲数)
        self.counts_per_rev = self.encoder_ppr * self.gear_ratio * 4
        # 轮子周长 (m)
        self.wheel_circumference = self.wheel_diameter * math.pi
        # 脉冲转米系数 (m / pulse)
        self.m_per_pulse = self.wheel_circumference / self.counts_per_rev

    def pulses_to_m(self, pulses):
        """将脉冲数转换为米"""
        return pulses * self.m_per_pulse

    def m_to_pulses(self, meters):
        """将米转换为脉冲数"""
        return meters / self.m_per_pulse

    def velocity_pulses_to_m_s(self, pulse_speed, dt_s):
        """将脉冲速度(pulses/dt)转换为物理速度(m/s)"""
        return self.pulses_to_m(pulse_speed) / dt_s

    def velocity_m_s_to_pulses(self, m_s_speed, dt_s):
        """将物理速度(m/s)转换为脉冲速度(pulses/dt)"""
        return self.m_to_pulses(m_s_speed) * dt_s

    def forward_kinematics(self, vm, vl, vr):
        """
        前向运动学: 轮速 -> 机器人体坐标系速度
        输入输出单位一致
        """
        # vx = 0.5 * (vl + vr) - vm
        # vy = (sqrt(3)/2) * (vl - vr)
        # omega = vl + vr + vm
        vx = 0.5 * (vl + vr) - vm
        vy = (math.sqrt(3) / 2.0) * (vl - vr)
        omega = vl + vr + vm
        return vx, vy, omega

    def inverse_kinematics(self, vx, vy, omega):
        """
        逆运动学: 机器人体坐标系速度 -> 轮速
        输入输出单位一致
        """
        inv_3 = 1.0 / 3.0
        sqrt3_3 = math.sqrt(3) * inv_3

        vl = (vx * inv_3) + (sqrt3_3 * vy) + (omega * inv_3)
        vr = (vx * inv_3) - (sqrt3_3 * vy) + (omega * inv_3)
        vm = (-2.0 * inv_3 * vx) + (omega * inv_3)

        return vm, vl, vr


class Odometry:
    """
    里程计，用于追踪世界坐标系下的位置
    """

    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def update(self, vx_robot, vy_robot, theta_rad, dt):
        """
        更新位置
        :param vx_robot: 机器人坐标系 X 速度 (m/s)
        :param vy_robot: 机器人坐标系 Y 速度 (m/s)
        :param theta_rad: 机器人当前朝向 (弧度)
        :param dt: 时间间隔 (s)
        """
        cos_t = math.cos(theta_rad)
        sin_t = math.sin(theta_rad)

        # 旋转到世界坐标系
        # 假设机器人坐标系 X 前, Y 左
        # 世界坐标系 X 对应 theta=0 的方向
        v_world_x = vx_robot * cos_t - vy_robot * sin_t
        v_world_y = vx_robot * sin_t + vy_robot * cos_t

        self.x += v_world_x * dt
        self.y += v_world_y * dt

    def reset(self, x=0.0, y=0.0):
        self.x = x
        self.y = y
