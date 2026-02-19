"""IMU 工厂函数."""
from seekfree import IMU660RX
from typing import Any


def create_imu() -> Any:
    """创建并初始化 IMU660RX 惯性测量单元.
    
    IMU660RX 提供三轴加速度计、三轴陀螺仪和温度传感器.
    
    返回:
        IMU660RX 对象,已初始化完成.
    """
    return IMU660RX()
