"""辅车运行时公开入口

@file src/assistant/__init__.py
"""

__all__ = ("AssistantApp",)


def __getattr__(name):
    if name == "AssistantApp":
        from assistant.app import AssistantApp

        return AssistantApp
    raise AttributeError(name)
