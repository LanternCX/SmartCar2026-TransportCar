"""启动阶段车辆角色状态.

提供 boot 与正常运行脚本之间共享的显式角色接口。
"""

_vehicle_role = None


def set_vehicle_role(role):
    """写入当前启动阶段识别出的车辆角色."""
    global _vehicle_role
    _vehicle_role = role


def get_vehicle_role():
    """读取当前启动阶段暴露的车辆角色."""
    if _vehicle_role is None:
        raise RuntimeError("VEHICLE_ROLE is not exposed")
    return _vehicle_role


def clear_vehicle_role():
    """清空当前启动阶段角色状态."""
    global _vehicle_role
    _vehicle_role = None
