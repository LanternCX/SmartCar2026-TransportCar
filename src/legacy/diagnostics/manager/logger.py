"""@brief 轻量 logger 包装器.

将模块名与 `LogManager` 绑定, 复用统一的等级派发逻辑.
"""

from config.params import LOG_DEBUG, LOG_ERROR, LOG_FATAL, LOG_INFO, LOG_TRACE, LOG_WARN


class Logger:
    """@brief 面向单个模块名的轻量 logger."""

    def __init__(self, manager, module_name: str) -> None:
        """@brief 初始化 logger.

        @param manager 日志管理器
        @param module_name 当前 logger 绑定的模块名
        """
        self._manager = manager
        self._module_name = module_name

    def log(self, level: int, message: str) -> None:
        """@brief 按指定等级输出日志."""
        self._manager.emit(level, self._module_name, message)

    def trace(self, message: str) -> None:
        """@brief 输出 TRACE 日志."""
        self.log(LOG_TRACE, message)

    def debug(self, message: str) -> None:
        """@brief 输出 DEBUG 日志."""
        self.log(LOG_DEBUG, message)

    def info(self, message: str) -> None:
        """@brief 输出 INFO 日志."""
        self.log(LOG_INFO, message)

    def warn(self, message: str) -> None:
        """@brief 输出 WARN 日志."""
        self.log(LOG_WARN, message)

    def error(self, message: str) -> None:
        """@brief 输出 ERROR 日志."""
        self.log(LOG_ERROR, message)

    def fatal(self, message: str) -> None:
        """@brief 输出 FATAL 日志."""
        self.log(LOG_FATAL, message)
