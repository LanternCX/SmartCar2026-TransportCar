"""@brief 日志配置与过滤规则.

集中保存日志档位, 模块过滤和查询响应拼装逻辑, 避免公开入口重新膨胀.
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


PROFILE_DEFAULTS = {
    "RUN": ("INFO", "off"),
    "DIAG": ("DEBUG", "off"),
}
CUSTOM_PROFILE_NAME = "CUSTOM"


def profile_defaults(profile_name: str = "RUN"):
    """@brief 返回指定档位的默认配置.

    @param profile_name 档位名
    @return `(normalized, level_name, level, filter_mode)`
    """
    normalized = normalize_upper_token(profile_name)
    defaults = PROFILE_DEFAULTS.get(normalized)
    if defaults is None:
        raise ValueError("invalid log profile: %s" % profile_name)
    level_name, filter_mode = defaults
    level = level_value_from_name(level_name)
    if level is None:
        raise ValueError("invalid log level: %s" % level_name)
    return normalized, level_name, level, filter_mode


def level_name_from_value(level: int):
    """@brief 按数值返回日志等级名."""
    if level == LOG_TRACE:
        return "TRACE"
    if level == LOG_DEBUG:
        return "DEBUG"
    if level == LOG_INFO:
        return "INFO"
    if level == LOG_WARN:
        return "WARN"
    if level == LOG_ERROR:
        return "ERROR"
    if level == LOG_FATAL:
        return "FATAL"
    return None


def level_value_from_name(level_name: str):
    """@brief 按等级名返回日志等级数值."""
    if level_name == "TRACE":
        return LOG_TRACE
    if level_name == "DEBUG":
        return LOG_DEBUG
    if level_name == "INFO":
        return LOG_INFO
    if level_name == "WARN":
        return LOG_WARN
    if level_name == "ERROR":
        return LOG_ERROR
    if level_name == "FATAL":
        return LOG_FATAL
    return None


def validate_filter_mode(filter_mode: str, raw_value: str) -> None:
    """@brief 校验过滤模式.

    @param filter_mode 规整后的模式值
    @param raw_value 原始输入, 用于报错
    """
    if filter_mode in ("off", "whitelist", "blacklist"):
        return
    raise ValueError("invalid filter_mode: %s" % raw_value)


def build_query_response(manager) -> str:
    """@brief 构建当前日志配置查询响应."""
    modules_text = "none"
    if manager.filter_modules:
        modules_text = "|".join(manager.filter_modules)
    return "?log=profile:%s,level:%s,filter:%s,color:%d,modules:%s\r\n" % (
        manager.profile_name.lower(),
        manager.level_name.lower(),
        manager.filter_mode,
        1 if manager.color_enabled else 0,
        modules_text,
    )


def module_allowed(filter_mode: str, filter_modules, module_name: str) -> bool:
    """@brief 按过滤模式检查模块是否允许输出."""
    matched = False
    for prefix in filter_modules:
        if matches_module_prefix(module_name, prefix):
            matched = True
            break
    if filter_mode == "off":
        return True
    if filter_mode == "whitelist":
        return matched
    if filter_mode == "blacklist":
        return not matched
    return False


def mark_profile_custom(manager) -> None:
    """@brief 在手工覆盖预设后标记自定义档位."""
    if manager._profile_name in PROFILE_DEFAULTS:
        manager._profile_name = CUSTOM_PROFILE_NAME


def matches_module_prefix(module_name: str, prefix: str) -> bool:
    """@brief 按点号边界判断模块前缀是否匹配."""
    if module_name == prefix:
        return True
    return module_name.startswith(prefix + ".")


def normalize_upper_token(value: str) -> str:
    """@brief 将文本参数规整为大写 token."""
    return str(value).strip().upper()


def normalize_lower_token(value: str) -> str:
    """@brief 将文本参数规整为小写 token."""
    return str(value).strip().lower()


def normalize_module_name(module_name: str) -> str:
    """@brief 规整单个模块名并去掉空白项."""
    return str(module_name).strip()
