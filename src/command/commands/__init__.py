"""
@brief 命令处理器包: 自动发现并导入所有 cmd_* 模块

每个模块在导入时通过 ``@router.command()`` 装饰器自动完成注册, 无需手动维护处理器列表

新增命令步骤(仅需一步):
    在本目录创建 ``cmd_xxx.py``, 使用 ``@router.command("key")`` 装饰 handle 函数
    包初始化时会自动发现并导入该文件, 装饰器触发注册
"""

import os
import sys


def _autodiscover():
    """
    @brief 扫描当前包目录, 自动导入所有 cmd_*.py 命令模块

    @details
    通过 __file__ 定位包目录, 兼容 CPython 和 MicroPython 两种环境的路径分隔符.
    每个导入的模块在加载时触发其模块级的 @router 装饰器, 将 handle 函数自动
    注册到全局单例路由器实例中, 无需显式维护命令列表

    @note 异常时静默继续, 确保包初始化不失败, 但命令可能无法加载
    """
    pkg_file = __file__
    if "/" in pkg_file:
        pkg_dir = pkg_file.rsplit("/", 1)[0]
    elif "\\" in pkg_file:
        pkg_dir = pkg_file.rsplit("\\", 1)[0]
    else:
        pkg_dir = "."

    try:
        seen = set()
        for fname in sorted(os.listdir(pkg_dir)):
            if fname.endswith(".py"):
                stem = fname[:-3]
            elif fname.endswith(".mpy"):
                stem = fname[:-4]
            else:
                continue
            if stem in seen:
                continue
            seen.add(stem)
            if stem.startswith("cmd_"):
                modname = __name__ + "." + stem
                if modname not in sys.modules:
                    __import__(modname)
    except Exception:
        pass


_autodiscover()
