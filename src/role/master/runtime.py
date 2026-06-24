"""主车角色运行入口

@file src/role/master/runtime.py
"""

from role.master.forward_runtime import MasterForwardRuntime


def create_transport_car() -> MasterForwardRuntime:
    """创建主车角色运行时对象

    @return 主车专用运行时实例
    """

    return MasterForwardRuntime()
