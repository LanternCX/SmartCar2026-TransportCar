"""命令与查询 handler 自动发现入口."""

import os
import sys


def _autodiscover() -> None:
    """自动导入所有 handler 模块, 注册失败时立即报错."""
    pkg_file = __file__
    if "/" in pkg_file:
        pkg_dir = pkg_file.rsplit("/", 1)[0]
    elif "\\" in pkg_file:
        pkg_dir = pkg_file.rsplit("\\", 1)[0]
    else:
        pkg_dir = "."

    for fname in sorted(os.listdir(pkg_dir)):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        if fname.startswith("cmd_") or fname.startswith("query_"):
            modname = __name__ + "." + fname[:-3]
            if modname not in sys.modules:
                __import__(modname)


_autodiscover()
