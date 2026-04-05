"""辅车运行时公开入口

@file src/assistant/__init__.py
"""

__all__ = ("AssistantApp",)


def __getattr__(name):
    """延迟暴露辅车应用入口

    @brief 让外部只在真正取用时加载主应用模块, 保持板端启动入口轻量。
    @param name 请求的公开对象名
    @return object
    """

    if name == "AssistantApp":
        from assistant.app import AssistantApp

        return AssistantApp
    raise AttributeError(name)
