"""按角色装配角色运行入口

根据识别到的角色创建对应的车体实例
"""

from role.vehicle_role import ROLE_ASSISTANT, ROLE_MASTER


def create_role_transport_car(role: str):
    """按角色创建当前运行链使用的车体实例

    @param role 车辆角色标识
    @return 对应角色的车体运行时实例
    @exception ValueError 当角色标识未知时抛出
    """

    if role == ROLE_MASTER:
        from role.master import create_transport_car

        return create_transport_car()
    if role == ROLE_ASSISTANT:
        from role.assistant import create_transport_car

        return create_transport_car()

    raise ValueError("unknown vision runtime role: %s" % role)
