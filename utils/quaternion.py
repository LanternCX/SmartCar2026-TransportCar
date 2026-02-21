"""四元数与姿态估计模块.

提供四元数基本操作、欧拉角转换和向量旋转等功能.
"""
import math
 


class Quaternion:
    """表示 3D 旋转的四元数.
    
    四元数形式为 q = (w, x, y, z),其中 w 为标量部分.
    """

    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        """初始化四元数.
        
        参数:
            w: 标量部分(默认 1.0 表示单位四元数).
            x, y, z: 向量部分.
        """
        self.w = w
        self.x = x
        self.y = y
        self.z = z

    def normalize(self):
        """将四元数归一化.
        
        副作用:
            修改四元数的各分量.
        """
        norm = math.sqrt(
            self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z
        )
        if norm == 0:
            return
        inv_norm = 1.0 / norm
        self.w *= inv_norm
        self.x *= inv_norm
        self.y *= inv_norm
        self.z *= inv_norm

    def update(self, gx, gy, gz, dt):
        """使用角速度更新四元数.
        
        四元数运动学:q_dot = 0.5 * q * omega,其中 omega = (0, gx, gy, gz).
        
        参数:
            gx, gy, gz: 角速度(弧度/秒).
            dt: 时间增量(秒).
        
        副作用:
            修改四元数分量.
        """
        q0, q1, q2, q3 = self.w, self.x, self.y, self.z

        # dQ = 0.5 * Q * Omega
        dq0 = 0.5 * (-q1 * gx - q2 * gy - q3 * gz)
        dq1 = 0.5 * (q0 * gx + q2 * gz - q3 * gy)
        dq2 = 0.5 * (q0 * gy - q1 * gz + q3 * gx)
        dq3 = 0.5 * (q0 * gz + q1 * gy - q2 * gx)

        self.w += dq0 * dt
        self.x += dq1 * dt
        self.y += dq2 * dt
        self.z += dq3 * dt
        self.normalize()

    def to_euler_yaw(self):
        """提取偏航角(绕 Z 轴旋转).
        
        返回:
            偏航角(弧度).
        """
        # Yaw = atan2(2(q0q3 + q1q2), 1 - 2(q2^2 + q3^2))
        return math.atan2(
            2.0 * (self.w * self.z + self.x * self.y),
            1.0 - 2.0 * (self.y * self.y + self.z * self.z),
        )

    def to_euler_angles(self):
        """转换为欧拉角.
        
        使用 Z-Y-X 约定(Yaw-Pitch-Roll).
        
        返回:
            元组 (roll, pitch, yaw),均为弧度.
        """
        w, x, y, z = self.w, self.x, self.y, self.z

        # Roll (绕 X 轴旋转)
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (绕 Y 轴旋转)
        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)

        # Yaw (绕 Z 轴旋转)
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    def rotate(self, v):
        """使用四元数旋转向量.
        
        计算 v_new = q * v * q_conj.
        
        参数:
            v: 向量 (x, y, z).
        
        返回:
            旋转后的向量 (rx, ry, rz).
        """
        vx, vy, vz = v
        w, x, y, z = self.w, self.x, self.y, self.z

        # 预计算常用项
        ww = w * w
        xx = x * x
        yy = y * y
        zz = z * z
        wx = w * x
        wy = w * y
        wz = w * z
        xy = x * y
        xz = x * z
        yz = y * z

        # 应用旋转矩阵(由四元数导出)
        # 列 0
        rx = (1 - 2 * (yy + zz)) * vx + 2 * (xy - wz) * vy + 2 * (xz + wy) * vz
        # 列 1
        ry = 2 * (xy + wz) * vx + (1 - 2 * (xx + zz)) * vy + 2 * (yz - wx) * vz
        # 列 2
        rz = 2 * (xz - wy) * vx + 2 * (yz + wx) * vy + (1 - 2 * (xx + yy)) * vz

        return rx, ry, rz

    def rotate_inv(self, v):
        """使用四元数的共轭(逆)旋转向量.
        
        计算 v_new = q_conj * v * q.
        若四元数表示世界坐标系到机器人坐标系的旋转,则此方法将向量
        从机器人坐标系变换到世界坐标系.
        
        参数:
            v: 向量 (x, y, z).
        
        返回:
            旋转后的向量 (rx, ry, rz).
        """
        vx, vy, vz = v
        # 共轭四元数:(w, -x, -y, -z)
        w, x, y, z = self.w, -self.x, -self.y, -self.z

        # 使用共轭分量的相同公式
        ww = w * w
        xx = x * x
        yy = y * y
        zz = z * z
        wx = w * x
        wy = w * y
        wz = w * z
        xy = x * y
        xz = x * z
        yz = y * z

        rx = (1 - 2 * (yy + zz)) * vx + 2 * (xy - wz) * vy + 2 * (xz + wy) * vz
        ry = 2 * (xy + wz) * vx + (1 - 2 * (xx + zz)) * vy + 2 * (yz - wx) * vz
        rz = 2 * (xz - wy) * vx + 2 * (yz + wx) * vy + (1 - 2 * (xx + yy)) * vz

        return rx, ry, rz

    def from_euler(self, roll, pitch, yaw):
        """从欧拉角初始化四元数.
        
        使用 Z-Y-X 序列(Yaw, Pitch, Roll).
        
        参数:
            roll: 滚转角(弧度).
            pitch: 俯仰角(弧度).
            yaw: 偏航角(弧度).
        
        副作用:
            修改四元数分量.
        """
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        self.w = cr * cp * cy + sr * sp * sy
        self.x = sr * cp * cy - cr * sp * sy
        self.y = cr * sp * cy + sr * cp * sy
        self.z = cr * cp * sy - sr * sp * cy
        self.normalize()
