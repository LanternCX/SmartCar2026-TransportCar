"""辅车视觉运行入口

@file src/vision/assistant/runtime.py
"""

from vision.assistant.follow_runtime import AssistantFollowRuntime


def create_transport_car() -> AssistantFollowRuntime:
    """创建辅车角色运行时对象

    @brief 给角色分发入口返回辅车专用运行时
    """

    return AssistantFollowRuntime()
