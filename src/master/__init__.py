"""主车运行时公开入口

@file src/master/__init__.py
"""

__all__ = ("MasterApp",)


def __getattr__(name):
    if name == "MasterApp":
        from master.app import MasterApp

        return MasterApp
    raise AttributeError(name)
