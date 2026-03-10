"""全局日志核心.

负责日志等级判断、模块过滤、格式化和 sink 分发.
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
from diagnostics.format import LogRecord, format_log_record
from diagnostics.sink import UartSink


VALID_FILTER_MODES = ("off", "whitelist", "blacklist")
LEVEL_NAME_TO_VALUE = {
    "TRACE": LOG_TRACE,
    "DEBUG": LOG_DEBUG,
    "INFO": LOG_INFO,
    "WARN": LOG_WARN,
    "ERROR": LOG_ERROR,
    "FATAL": LOG_FATAL,
}
LEVEL_VALUE_TO_NAME = {
    LOG_TRACE: "TRACE",
    LOG_DEBUG: "DEBUG",
    LOG_INFO: "INFO",
    LOG_WARN: "WARN",
    LOG_ERROR: "ERROR",
    LOG_FATAL: "FATAL",
}
PROFILE_DEFAULTS = {
    "RUN": ("INFO", "off"),
    "DIAG": ("DEBUG", "off"),
}
CUSTOM_PROFILE_NAME = "CUSTOM"


class SinkLike:
    """日志 sink 协议."""

    def write(self, text: str) -> None:
        """写入一条日志文本."""
        raise NotImplementedError


class RecordSinkLike:
    """支持按等级写入的扩展 sink 协议."""

    def write_record(self, level: int, text: str) -> None:
        """按等级写入日志文本."""
        raise NotImplementedError


class QueryUARTLike:
    """查询响应串口协议."""

    def write(self, text: str) -> None:
        """写入查询响应文本."""
        raise NotImplementedError


class LogCommandContext:
    """日志命令处理器需要的最小上下文协议."""

    logger_manager: "LogManager"


class LogQueryContext(LogCommandContext):
    """日志查询处理器需要的最小上下文协议."""

    def get_query_uart(self):
        """返回查询响应串口."""
        raise NotImplementedError


class SnapshotBuilder:
    """诊断快照构造器占位协议."""

    def __call__(self):
        """返回一份快照字典."""
        raise NotImplementedError


class LogManager:
    """管理运行时日志配置与 logger 创建."""

    def __init__(
        self,
        level: int = LOG_LEVEL_DEFAULT,
        color_enabled: bool = False,
        filter_mode: str = LOG_FILTER_MODE_DEFAULT,
        filter_modules=LOG_FILTER_MODULES_DEFAULT,
        sinks=(),
    ) -> None:
        self.level = LOG_LEVEL_DEFAULT
        self.color_enabled = False
        self.filter_mode = LOG_FILTER_MODE_DEFAULT
        self.filter_modules = LOG_FILTER_MODULES_DEFAULT
        self._profile_name = "RUN"
        self.sinks = list(sinks)
        self.set_level(level)
        self.set_color_enabled(color_enabled)
        self.set_filter_mode(filter_mode)
        self.set_filter_modules(filter_modules)

    def get_logger(self, module_name: str) -> "Logger":
        """返回指定模块名的 logger."""
        return Logger(self, module_name)

    def should_emit(self, level: int, module_name: str) -> bool:
        """判断当前日志是否允许输出."""
        if level < self.level:
            return False
        return self._module_allowed(module_name)

    def emit(self, level: int, module_name: str, message: str) -> None:
        """向所有 sink 分发一条日志消息."""
        if not self.should_emit(level, module_name):
            return
        text = format_log_record(
            LogRecord(level=level, module_name=module_name, message=message),
            color_enabled=self.color_enabled,
        )
        for sink in self.sinks:
            write_record = getattr(sink, "write_record", None)
            if write_record is not None:
                write_record(level, text)
            else:
                sink.write(text)

    @property
    def level_name(self) -> str:
        """返回当前日志等级名."""
        return LEVEL_VALUE_TO_NAME[self.level]

    @property
    def profile_name(self) -> str:
        """返回当前日志配置档位名."""
        return self._profile_name

    def set_level(self, level: int) -> None:
        """按数值更新日志等级."""
        if level not in LEVEL_VALUE_TO_NAME:
            raise ValueError("invalid log level: %s" % level)
        self.level = level

    def set_profile(self, profile_name: str) -> None:
        """按预设档位更新日志等级与过滤模式."""
        normalized = _normalize_upper_token(profile_name)
        defaults = PROFILE_DEFAULTS.get(normalized)
        if defaults is None:
            raise ValueError("invalid log profile: %s" % profile_name)
        level_name, filter_mode = defaults
        self._profile_name = normalized
        self._set_level_name(level_name)
        self._set_filter_mode(filter_mode)

    def set_level_name(self, level_name: str) -> None:
        """按文本更新日志等级."""
        changed = self._set_level_name(level_name)
        if changed:
            self._mark_profile_custom()

    def _set_level_name(self, level_name: str) -> bool:
        """按文本更新日志等级,并返回是否发生变化."""
        normalized = _normalize_upper_token(level_name)
        level = LEVEL_NAME_TO_VALUE.get(normalized)
        if level is None:
            raise ValueError("invalid log level: %s" % level_name)
        changed = self.level != level
        self.level = level
        return changed

    def set_filter_mode(self, filter_mode: str) -> None:
        """更新日志模块过滤模式."""
        changed = self._set_filter_mode(filter_mode)
        if changed:
            self._mark_profile_custom()

    def _set_filter_mode(self, filter_mode: str) -> bool:
        """更新日志模块过滤模式,并返回是否发生变化."""
        normalized = _normalize_lower_token(filter_mode)
        if normalized not in VALID_FILTER_MODES:
            raise ValueError("invalid filter_mode: %s" % filter_mode)
        changed = self.filter_mode != normalized
        self.filter_mode = normalized
        return changed

    def set_filter_modules(self, filter_modules) -> None:
        """更新日志模块过滤列表."""
        modules = []
        for module_name in filter_modules:
            normalized = _normalize_module_name(module_name)
            if normalized:
                modules.append(normalized)
        self.filter_modules = tuple(modules)

    def set_color_enabled(self, enabled: bool) -> None:
        """更新日志颜色开关."""
        self.color_enabled = bool(enabled)

    def reset_defaults(self) -> None:
        """恢复运行期日志默认配置."""
        self._profile_name = "RUN"
        self.set_level(LOG_LEVEL_DEFAULT)
        self._set_filter_mode(LOG_FILTER_MODE_DEFAULT)
        self.set_filter_modules(LOG_FILTER_MODULES_DEFAULT)
        self.set_color_enabled(False)

    def build_query_response(self) -> str:
        """构建当前日志配置查询响应."""
        modules_text = "none"
        if self.filter_modules:
            modules_text = "|".join(self.filter_modules)
        return "?log=profile:%s,level:%s,filter:%s,color:%d,modules:%s\r\n" % (
            self.profile_name.lower(),
            self.level_name.lower(),
            self.filter_mode,
            1 if self.color_enabled else 0,
            modules_text,
        )

    def _module_allowed(self, module_name: str) -> bool:
        """按过滤模式检查模块是否允许输出."""
        matched = False
        for prefix in self.filter_modules:
            if _matches_module_prefix(module_name, prefix):
                matched = True
                break

        if self.filter_mode == "off":
            return True
        if self.filter_mode == "whitelist":
            return matched
        if self.filter_mode == "blacklist":
            return not matched
        return False

    def _mark_profile_custom(self) -> None:
        """当手工覆盖预设派生配置时,标记为自定义档位."""
        if self._profile_name in PROFILE_DEFAULTS:
            self._profile_name = CUSTOM_PROFILE_NAME


class Logger:
    """面向单个模块名的轻量 logger."""

    def __init__(self, manager: LogManager, module_name: str) -> None:
        self._manager = manager
        self._module_name = module_name

    def log(self, level: int, message: str) -> None:
        """按指定等级输出日志."""
        self._manager.emit(level, self._module_name, message)

    def trace(self, message: str) -> None:
        """输出 TRACE 日志."""
        self.log(LOG_TRACE, message)

    def debug(self, message: str) -> None:
        """输出 DEBUG 日志."""
        self.log(LOG_DEBUG, message)

    def info(self, message: str) -> None:
        """输出 INFO 日志."""
        self.log(LOG_INFO, message)

    def warn(self, message: str) -> None:
        """输出 WARN 日志."""
        self.log(LOG_WARN, message)

    def error(self, message: str) -> None:
        """输出 ERROR 日志."""
        self.log(LOG_ERROR, message)

    def fatal(self, message: str) -> None:
        """输出 FATAL 日志."""
        self.log(LOG_FATAL, message)


def _matches_module_prefix(module_name: str, prefix: str) -> bool:
    """按点号边界判断模块前缀是否匹配."""
    if module_name == prefix:
        return True
    return module_name.startswith(prefix + ".")


def _normalize_upper_token(value: str) -> str:
    """将文本参数规整为大写 token."""
    return str(value).strip().upper()


def _normalize_lower_token(value: str) -> str:
    """将文本参数规整为小写 token."""
    return str(value).strip().lower()


def _normalize_module_name(module_name: str) -> str:
    """规整单个模块名并去掉空白项."""
    return str(module_name).strip()


def build_uart3_logger_manager(uart) -> LogManager:
    """为 uart3 构造默认日志管理器."""
    return LogManager(sinks=[UartSink(uart)])
