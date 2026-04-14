"""按角色装配视觉运行入口."""

from vision.vehicle_role import ROLE_ASSISTANT, ROLE_MASTER


def create_role_transport_car(role: str):
    """按角色创建当前运行链使用的车体实例."""

    if role == ROLE_MASTER:
        from vision.master import create_transport_car

        return create_transport_car()
    if role == ROLE_ASSISTANT:
        from vision.assistant import create_transport_car

        return create_transport_car()

    raise ValueError("unknown vision runtime role: %s" % role)
