"""IMU 工厂函数"""
from seekfree import IMU660RX


def create_imu():
    return IMU660RX()
