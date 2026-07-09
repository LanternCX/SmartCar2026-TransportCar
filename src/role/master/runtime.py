"""主车角色运行入口

@file src/role/master/runtime.py
"""

from utils.startup_log import log_memory


def create_transport_car():
    """创建主车角色运行时对象

    @return 主车专用运行时实例
    """

    log_memory("ri0")
    from role.master.forward_runtime import MasterForwardRuntime

    log_memory("ri1")
    return MasterForwardRuntime()
