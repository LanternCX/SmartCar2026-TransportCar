"""
@file src/vision/master/runtime.py
@brief 主车视觉运行入口
"""

from vision.master.forward_runtime import MasterForwardRuntime


def create_transport_car() -> MasterForwardRuntime:
    """
    @brief 创建主车角色运行时对象

    @return 主车专用运行时实例
    """

    return MasterForwardRuntime()
