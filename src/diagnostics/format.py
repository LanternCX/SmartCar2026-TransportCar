"""日志格式化工具.

提供可读的纯文本输出与可选 ANSI 颜色输出.
"""

from config.params import LOG_DEBUG, LOG_ERROR, LOG_FATAL, LOG_INFO, LOG_TRACE, LOG_WARN


LEVEL_PREFIX = {
    LOG_TRACE: "T",
    LOG_DEBUG: "D",
    LOG_INFO: "I",
    LOG_WARN: "W",
    LOG_ERROR: "E",
    LOG_FATAL: "F",
}

LEVEL_COLOR = {
    LOG_TRACE: "37",
    LOG_DEBUG: "36",
    LOG_INFO: "32",
    LOG_WARN: "33",
    LOG_ERROR: "31",
    LOG_FATAL: "35",
}

MODULE_COLUMN_WIDTH = 14


class LogRecord:
    """描述单条日志记录的只读数据."""

    __slots__ = ("level", "module_name", "message")

    def __init__(self, level: int, module_name: str, message: str) -> None:
        self.level = level
        self.module_name = module_name
        self.message = message


def sanitize_log_text(text: str) -> str:
    """将日志字段规整为单行 ASCII 文本."""
    chars = []
    for char in text:
        code = ord(char)
        if char == "\r" or char == "\n" or char == "\t":
            chars.append(" ")
        elif 32 <= code <= 126:
            chars.append(char)
        else:
            chars.append("?")
    return "".join(chars)


def format_module_name(module_name: str) -> str:
    """整理模块列, 过长时截断以保持可读性."""
    cleaned = sanitize_log_text(module_name)
    if len(cleaned) <= MODULE_COLUMN_WIDTH:
        return cleaned
    return cleaned[: MODULE_COLUMN_WIDTH - 1] + "+"


def format_log_record(record: LogRecord, color_enabled: bool = False) -> str:
    """按固定格式生成日志文本."""
    line = "%s [%-14s] %s" % (
        LEVEL_PREFIX.get(record.level, "?"),
        format_module_name(record.module_name),
        sanitize_log_text(record.message),
    )
    if color_enabled:
        color_code = LEVEL_COLOR.get(record.level)
        if color_code is not None:
            line = "\x1b[%sm%s\x1b[0m" % (color_code, line)
    return line + "\r\n"
