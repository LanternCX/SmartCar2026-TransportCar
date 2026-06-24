"""辅车角色运行入口

@file src/role/assistant/runtime.py
"""

from role.assistant.follow_runtime import AssistantFollowRuntime


def create_transport_car() -> AssistantFollowRuntime:
    """创建辅车角色运行时对象

    @return 辅车专用运行时实例
    """

    return AssistantFollowRuntime()
