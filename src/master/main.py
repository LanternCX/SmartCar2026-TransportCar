"""主车启动入口

@file src/master/main.py
"""

from master.app import MasterApp


def main():
    """创建主车最小应用

    @brief 返回主车运行时入口对象
    @return MasterApp
    """

    return MasterApp()
