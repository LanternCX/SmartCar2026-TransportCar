"""
命令处理器包:自动发现并导入所有 cmd_*.py / query_*.py 模块.

每个模块在导入时通过 ``@router.command()`` / ``@router.query()`` 装饰器
自动完成注册,无需手动维护处理器列表.

新增命令步骤(仅需一步):
    在本目录创建 ``cmd_xxx.py``,使用 ``@router.command("key")`` 装饰 handle 函数.
    包初始化时会自动发现并导入该文件,装饰器触发注册.
"""
import os
import sys


def _autodiscover() -> None:
    """
    扫描当前包目录,自动导入所有 cmd_*.py 和 query_*.py 命令模块.

    通过 __file__ 定位包目录,兼容 CPython 和 MicroPython 环境.
    导入时每个模块的 @router 装饰器自动将 handle 函数注册到单例路由器.
    """
    pkg_file = __file__
    # 兼容正斜杠(Linux/MicroPython)和反斜杠(Windows)
    if "/" in pkg_file:
        pkg_dir = pkg_file.rsplit("/", 1)[0]
    elif "\\" in pkg_file:
        pkg_dir = pkg_file.rsplit("\\", 1)[0]
    else:
        pkg_dir = "."

    try:
        for fname in sorted(os.listdir(pkg_dir)):
            if not fname.endswith(".py"):
                continue
            if fname.startswith("cmd_") or fname.startswith("query_"):
                modname = __name__ + "." + fname[:-3]
                if modname not in sys.modules:
                    __import__(modname)
    except Exception:
        pass


_autodiscover()
