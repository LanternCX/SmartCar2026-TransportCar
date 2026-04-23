"""IMU 工厂函数

封装 IMU660RX 惯性测量单元的初始化, 提供六轴姿态与温度数据
"""
from seekfree import IMU660RX


def create_imu():
    """@brief 创建并初始化 IMU660RX 惯性测量单元

    IMU660RX 集成三轴加速度计与三轴陀螺仪, 用于车体姿态解算与运动控制反馈

    @return 已初始化完成的 IMU660RX 对象
    """
    return IMU660RX()
