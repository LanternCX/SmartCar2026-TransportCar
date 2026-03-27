"""辅车启动入口

@file src/assistant/main.py
"""

from assistant.app import AssistantApp


def main():
    """创建辅车应用入口对象

    @brief 为启动脚本提供辅车应用实例
    @return AssistantApp
    """

    return AssistantApp()
