"""主车启动入口

@file src/master/main.py
"""

try:
    from master.app import MasterRuntimeLoop, build_hw_bundle
except ImportError:
    from app import MasterRuntimeLoop, build_hw_bundle


def main():
    """创建主车运行循环入口对象

    @brief 为启动脚本提供主车主线运行循环
    @return MasterRuntimeLoop
    """

    return MasterRuntimeLoop(build_hw_bundle()["uart"])
