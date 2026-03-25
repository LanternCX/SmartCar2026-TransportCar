"""辅车启动入口

@file src/assistant/main.py
"""

from assistant.app import AssistantApp


def main() -> AssistantApp:
    """创建辅车最小应用

    @brief 返回辅车运行时入口对象
    @return AssistantApp
    """

    return AssistantApp()
