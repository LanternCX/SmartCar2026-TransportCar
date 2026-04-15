"""主车视觉运行入口."""


def create_transport_car():
    """创建主车运行链当前使用的共享底盘实例."""

    from services.core import TransportCar

    return TransportCar()
