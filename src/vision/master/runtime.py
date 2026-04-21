"""主车视觉运行入口.

@file src/vision/master/runtime.py
"""

from vision.master.forward_runtime import MasterForwardRuntime


def create_transport_car() -> MasterForwardRuntime:
    """创建主车角色运行时对象.

    @brief 给角色分发入口返回主车专用运行时
    """

    return MasterForwardRuntime()
