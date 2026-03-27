"""主车启动入口

@file src/master/main.py
"""

from master.app import MasterApp


def main():
    """创建主车应用入口对象

    @brief 为启动脚本提供主车应用实例
    @return MasterApp
    """

    return MasterApp()
