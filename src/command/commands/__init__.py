"""
@brief 命令处理器包: 自动发现并导入所有 cmd_*.py / query_*.py 模块

每个模块在导入时通过 ``@router.command()`` / ``@router.query()`` 装饰器
自动完成注册, 无需手动维护处理器列表

新增命令步骤(仅需一步):
    在本目录创建 ``cmd_xxx.py``, 使用 ``@router.command("key")`` 装饰 handle 函数
    包初始化时会自动发现并导入该文件, 装饰器触发注册
"""

import os
import sys


def _autodiscover():
    """
    @brief 扫描当前包目录, 自动导入所有 cmd_*.py 和 query_*.py 命令模块

    @details
    通过 __file__ 定位包目录, 兼容 CPython 和 MicroPython 两种环境的路径分隔符
    每个导入的模块在加载时触发其模块级的 @router 装饰器, 将 handle 函数自动
    注册到全局单例路由器实例中, 无需显式维护命令列表

    @note 异常时静默继续, 确保包初始化不失败, 但命令可能无法加载
    """
    pkg_file = __file__
    # 兼容 Linux/MicroPython 的正斜杠和 Windows 的反斜杠路径分隔
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
                # 构造模块全路径名, 检查是否已加载以避免重复导入
                modname = __name__ + "." + fname[: -3]
                if modname not in sys.modules:
                    __import__(modname)
    except Exception:
        # 目录扫描失败或导入失败时静默处理, 不中断包初始化
        pass


_autodiscover()
