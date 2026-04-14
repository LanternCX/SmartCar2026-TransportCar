"""辅车视觉运行入口."""


def create_transport_car():
    """创建辅车运行链当前使用的车体实例."""

    from services.transport_car import TransportCar

    return TransportCar()
