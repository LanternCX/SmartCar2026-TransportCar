"""命令与查询 handler 显式加载入口."""

import os
import sys


def _iter_handler_module_names(prefixes) -> tuple:
    """按给定前缀返回待导入 handler 模块名列表."""
    pkg_file = __file__
    if "/" in pkg_file:
        pkg_dir = pkg_file.rsplit("/", 1)[0]
    elif "\\" in pkg_file:
        pkg_dir = pkg_file.rsplit("\\", 1)[0]
    else:
        pkg_dir = "."

    names = []
    for fname in sorted(os.listdir(pkg_dir)):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        matched = False
        for prefix in prefixes:
            if fname.startswith(prefix):
                matched = True
                break
        if matched:
            names.append(__name__ + "." + fname[:-3])
    return tuple(names)


def _autodiscover(prefixes) -> None:
    """按前缀自动导入 handler 模块, 注册失败时立即报错."""
    for modname in _iter_handler_module_names(prefixes):
        if modname not in sys.modules:
            __import__(modname)


def load_all_handlers() -> None:
    """导入全部命令与查询 handler, 供完整运行时装配使用."""
    _autodiscover(("cmd_", "query_"))


def load_query_handlers() -> None:
    """仅导入 query handler, 用于 Stage 2 lite 最小查询路径."""
    _autodiscover(("query_",))
