"""全向轮运动学与里程计模块.

实现全向轮运动学模型(前/逆向运动学)及单位转换,以及里程计用于追踪
世界坐标系下的位置.
"""
import math
from typing import Tuple


class OmniKinematics:
    """全向轮运动学模型及单位转换.
    
    基于三轮全向轮配置,提供脉冲/米单位转换以及
    轮速与机器人体坐标系速度的相互转换.
    """

    def __init__(self) -> None:
        """初始化运动学参数."""
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

    def pulses_to_m(self, pulses: float) -> float:
        """将脉冲数转换为米.
        
        参数:
            pulses: 脉冲数.
        
        返回:
            距离(米).
        """
        return pulses * self.m_per_pulse

    def m_to_pulses(self, meters: float) -> float:
        """将米转换为脉冲数.
        
        参数:
            meters: 距离(米).
        
        返回:
            脉冲数.
        """
        return meters / self.m_per_pulse

    def velocity_pulses_to_m_s(self, pulse_speed: float, dt_s: float) -> float:
        """将脉冲速度转换为物理速度.
        
        参数:
            pulse_speed: 脉冲速度(pulses/dt).
            dt_s: 时间增量(秒).
        
        返回:
            速度(m/s).
        """
        return self.pulses_to_m(pulse_speed) / dt_s

    def velocity_m_s_to_pulses(self, m_s_speed: float, dt_s: float) -> float:
        """将物理速度转换为脉冲速度.
        
        参数:
            m_s_speed: 速度(m/s).
            dt_s: 时间增量(秒).
        
        返回:
            脉冲速度(pulses/dt).
        """
        return self.m_to_pulses(m_s_speed) * dt_s

    def forward_kinematics(self, vm: float, vl: float, vr: float) -> Tuple[float, float, float]:
        """前向运动学:轮速 → 机器人体坐标系速度.
        
        输入输出单位一致.
        
        参数:
            vm: 中间轮速度.
            vl: 左轮速度.
            vr: 右轮速度.
        
        返回:
            元组 (vx, vy, omega),其中 vx 为纵向速度,vy 为横向速度,omega 为角速度.
        """
        vx = 0.5 * (vl + vr) - vm
        vy = (math.sqrt(3) / 2.0) * (vl - vr)
        omega = vl + vr + vm
        return vx, vy, omega

    def inverse_kinematics(self, vx: float, vy: float, omega: float) -> Tuple[float, float, float]:
        """逆向运动学:机器人体坐标系速度 → 轮速.
        
        输入输出单位一致.
        
        参数:
            vx: 纵向速度.
            vy: 横向速度.
            omega: 角速度.
        
        返回:
            元组 (vm, vl, vr),分别为中间、左、右轮速度.
        """
        inv_3 = 1.0 / 3.0
        sqrt3_3 = math.sqrt(3) * inv_3

        vl = (vx * inv_3) + (sqrt3_3 * vy) + (omega * inv_3)
        vr = (vx * inv_3) - (sqrt3_3 * vy) + (omega * inv_3)
        vm = (-2.0 * inv_3 * vx) + (omega * inv_3)

        return vm, vl, vr


class Odometry:
    """里程计,用于追踪世界坐标系下的位置.
    
    积分机器人体坐标系速度并根据朝向转换到世界坐标系.
    """

    def __init__(self) -> None:
        """初始化里程计状态."""
        self.x = 0.0
        self.y = 0.0

    def update(self, vx_robot: float, vy_robot: float, theta_rad: float, dt: float) -> None:
        """更新位置.
        
        参数:
            vx_robot: 机器人坐标系 X 速度 (m/s).
            vy_robot: 机器人坐标系 Y 速度 (m/s).
            theta_rad: 机器人当前朝向 (弧度).
            dt: 时间间隔 (s).
        
        副作用:
            修改 self.x 和 self.y.
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

    def reset(self, x: float = 0.0, y: float = 0.0) -> None:
        """重置里程计.
        
        参数:
            x: 新的 X 坐标.
            y: 新的 Y 坐标.
        """
        self.x = x
        self.y = y
