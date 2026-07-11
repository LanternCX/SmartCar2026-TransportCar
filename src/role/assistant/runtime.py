"""辅车角色运行入口

@file src/role/assistant/runtime.py
"""

# from utils.startup_log import log_memory


def create_transport_car():
    """创建辅车角色运行时对象

    @return 辅车专用运行时实例
    """

    # log_memory("ai0")
    from role.assistant.follow_runtime import AssistantFollowRuntime

    # log_memory("ai1")
    return AssistantFollowRuntime()
