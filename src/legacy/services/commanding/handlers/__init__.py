"""命令与查询 handler 显式加载入口."""

import sys


ALL_HANDLER_MODULES = (
    __name__ + ".cmd_angle",
    __name__ + ".cmd_d_angle",
    __name__ + ".cmd_dx",
    __name__ + ".cmd_dy",
    __name__ + ".cmd_log_color",
    __name__ + ".cmd_log_filter",
    __name__ + ".cmd_log_level",
    __name__ + ".cmd_log_modules",
    __name__ + ".cmd_log_profile",
    __name__ + ".cmd_log_reset",
    __name__ + ".cmd_omega",
    __name__ + ".cmd_print",
    __name__ + ".cmd_rear",
    __name__ + ".cmd_reset",
    __name__ + ".cmd_vx",
    __name__ + ".cmd_vy",
    __name__ + ".cmd_x",
    __name__ + ".cmd_y",
    __name__ + ".query_enc",
    __name__ + ".query_health",
    __name__ + ".query_imu",
    __name__ + ".query_lock",
    __name__ + ".query_log",
    __name__ + ".query_motor",
    __name__ + ".query_pos",
    __name__ + ".query_tick",
    __name__ + ".query_vision",
)

QUERY_HANDLER_START_INDEX = 18


def _import_handler_module(modname: str) -> None:
    """按模块名导入 handler, 供显式装配复用."""
    if modname not in sys.modules:
        __import__(modname)


def _load_modules(modnames, start_index: int = 0, stop_index=None) -> None:
    """按给定模块元组导入 handler, 注册失败时立即报错."""
    if stop_index is None:
        stop_index = len(modnames)
    for index in range(start_index, stop_index):
        _import_handler_module(modnames[index])


def load_all_handlers() -> None:
    """导入全部命令与查询 handler, 供完整运行时装配使用."""
    _load_modules(ALL_HANDLER_MODULES)


def load_command_handlers() -> None:
    """仅导入 command handler, 用于运行时按需装配."""
    _load_modules(ALL_HANDLER_MODULES, stop_index=QUERY_HANDLER_START_INDEX)


def load_query_handlers() -> None:
    """仅导入 query handler, 用于 Stage 2 lite 最小查询路径."""
    _load_modules(ALL_HANDLER_MODULES, start_index=QUERY_HANDLER_START_INDEX)
