"""@brief 日志管理公开入口.

保留 `diagnostics.manager` 的兼容导入路径, 将配置判断, 发射流程和 logger
包装分别下沉到分包内部模块.
"""

from config.params import (
    LOG_DEBUG,
    LOG_ERROR,
    LOG_FATAL,
    LOG_FILTER_MODE_DEFAULT,
    LOG_FILTER_MODULES_DEFAULT,
    LOG_INFO,
    LOG_LEVEL_DEFAULT,
    LOG_TRACE,
    LOG_WARN,
)
from diagnostics.format import format_log_record
from diagnostics.manager.config import (
    build_query_response,
    level_name_from_value,
    level_value_from_name,
    mark_profile_custom,
    module_allowed,
    normalize_lower_token,
    normalize_module_name,
    normalize_upper_token,
    profile_defaults,
    validate_filter_mode,
)
from diagnostics.manager.emit import emit_record
from diagnostics.manager.logger import Logger
from diagnostics.sink import UartSink


class LogManager:
    """@brief 管理运行时日志配置与 logger 创建."""

    def __init__(
        self,
        level: int = LOG_LEVEL_DEFAULT,
        color_enabled: bool = False,
        filter_mode: str = LOG_FILTER_MODE_DEFAULT,
        filter_modules=LOG_FILTER_MODULES_DEFAULT,
        sinks=(),
        oom_callback=None,
    ) -> None:
        """@brief 初始化日志管理器.

        @param level 初始日志等级
        @param color_enabled 是否启用 ANSI 颜色
        @param filter_mode 模块过滤模式
        @param filter_modules 模块过滤列表
        @param sinks 输出 sink 列表
        @param oom_callback OOM 事件回调
        """
        self.level = LOG_LEVEL_DEFAULT
        self.color_enabled = False
        self.filter_mode = LOG_FILTER_MODE_DEFAULT
        self.filter_modules = LOG_FILTER_MODULES_DEFAULT
        self._profile_name = "RUN"
        self._last_logger = None
        self._last_logger_module_name = None
        self.sinks = list(sinks)
        self._oom_callback = oom_callback
        self.set_level(level)
        self.set_color_enabled(color_enabled)
        self.set_filter_mode(filter_mode)
        self.set_filter_modules(filter_modules)

    def get_logger(self, module_name: str) -> Logger:
        """@brief 返回指定模块名的 logger."""
        if self._last_logger_module_name == module_name:
            logger = self._last_logger
            if logger is not None:
                return logger
        logger = Logger(self, module_name)
        self._last_logger = logger
        self._last_logger_module_name = module_name
        return logger

    def should_emit(self, level: int, module_name: str) -> bool:
        """@brief 判断当前日志是否允许输出."""
        if level < self.level:
            return False
        return module_allowed(self.filter_mode, self.filter_modules, module_name)

    def emit(self, level: int, module_name: str, message: str) -> None:
        """@brief 向所有 sink 分发一条日志消息."""
        emit_record(self, level, module_name, message)

    @property
    def level_name(self) -> str:
        """@brief 返回当前日志等级名."""
        level_name = level_name_from_value(self.level)
        if level_name is None:
            raise ValueError("invalid log level: %s" % self.level)
        return level_name

    @property
    def profile_name(self) -> str:
        """@brief 返回当前日志配置档位名."""
        return self._profile_name

    def set_level(self, level: int) -> None:
        """@brief 按数值更新日志等级."""
        if level_name_from_value(level) is None:
            raise ValueError("invalid log level: %s" % level)
        self.level = level

    def set_profile(self, profile_name: str) -> None:
        """@brief 按预设档位更新日志等级与过滤模式."""
        normalized, level_name, _level, filter_mode = profile_defaults(profile_name)
        self._profile_name = normalized
        self._set_level_name(level_name)
        self._set_filter_mode(filter_mode)

    def set_level_name(self, level_name: str) -> None:
        """@brief 按文本更新日志等级."""
        if self._set_level_name(level_name):
            mark_profile_custom(self)

    def _set_level_name(self, level_name: str) -> bool:
        """@brief 按文本更新日志等级并返回是否变化."""
        normalized = normalize_upper_token(level_name)
        level = level_value_from_name(normalized)
        if level is None:
            raise ValueError("invalid log level: %s" % level_name)
        changed = self.level != level
        self.level = level
        return changed

    def set_filter_mode(self, filter_mode: str) -> None:
        """@brief 更新日志模块过滤模式."""
        if self._set_filter_mode(filter_mode):
            mark_profile_custom(self)

    def _set_filter_mode(self, filter_mode: str) -> bool:
        """@brief 更新过滤模式并返回是否变化."""
        normalized = normalize_lower_token(filter_mode)
        validate_filter_mode(normalized, filter_mode)
        changed = self.filter_mode != normalized
        self.filter_mode = normalized
        return changed

    def set_filter_modules(self, filter_modules) -> None:
        """@brief 更新日志模块过滤列表."""
        modules = []
        for module_name in filter_modules:
            normalized = normalize_module_name(module_name)
            if normalized:
                modules.append(normalized)
        self.filter_modules = tuple(modules)

    def set_color_enabled(self, enabled: bool) -> None:
        """@brief 更新日志颜色开关."""
        self.color_enabled = bool(enabled)

    def reset_defaults(self) -> None:
        """@brief 恢复运行期日志默认配置."""
        normalized, _level_name, level, filter_mode = profile_defaults()
        self._profile_name = normalized
        self.set_level(level)
        self._set_filter_mode(filter_mode)
        self.set_filter_modules(LOG_FILTER_MODULES_DEFAULT)
        self.set_color_enabled(False)

    def build_query_response(self) -> str:
        """@brief 构建当前日志配置查询响应."""
        return build_query_response(self)


def build_uart3_logger_manager(uart, oom_callback=None) -> LogManager:
    """@brief 为 uart3 构造默认日志管理器."""
    return LogManager(sinks=[UartSink(uart)], oom_callback=oom_callback)
