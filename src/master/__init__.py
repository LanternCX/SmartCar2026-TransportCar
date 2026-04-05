"""主车运行时公开入口

@file src/master/__init__.py

负责把主车主链对外收口为稳定导入入口, 让上层只暴露 `MasterApp`。
"""

# 对外仅公开主车应用编排入口, 其余实现细节继续留在子模块内
__all__ = ("MasterApp",)


def __getattr__(name):
    if name == "MasterApp":
        from master.app import MasterApp

        return MasterApp
    raise AttributeError(name)
