"""日志格式化工具.

提供可读的纯文本输出与可选 ANSI 颜色输出.
"""

from config.params import LOG_DEBUG, LOG_ERROR, LOG_FATAL, LOG_INFO, LOG_TRACE, LOG_WARN


MODULE_COLUMN_WIDTH = 14


def _level_prefix(level: int) -> str:
    """返回日志等级前缀字符."""
    if level == LOG_TRACE:
        return "T"
    if level == LOG_DEBUG:
        return "D"
    if level == LOG_INFO:
        return "I"
    if level == LOG_WARN:
        return "W"
    if level == LOG_ERROR:
        return "E"
    if level == LOG_FATAL:
        return "F"
    return "?"


def _level_color(level: int):
    """返回日志等级对应的 ANSI 颜色码."""
    if level == LOG_TRACE:
        return "37"
    if level == LOG_DEBUG:
        return "36"
    if level == LOG_INFO:
        return "32"
    if level == LOG_WARN:
        return "33"
    if level == LOG_ERROR:
        return "31"
    if level == LOG_FATAL:
        return "35"
    return None


def sanitize_log_text(text: str) -> str:
    """将日志字段规整为单行 ASCII 文本."""
    text = str(text)
    clean = True
    for char in text:
        code = ord(char)
        if char == "\r" or char == "\n" or char == "\t":
            clean = False
            break
        if code < 32 or code > 126:
            clean = False
            break
    if clean:
        return text

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


def format_log_record(
    level: int,
    module_name: str,
    message: str,
    color_enabled: bool = False,
) -> str:
    """按固定格式生成日志文本."""
    clean_module_name = sanitize_log_text(module_name)
    clean_message = sanitize_log_text(message)
    if len(clean_module_name) > MODULE_COLUMN_WIDTH:
        clean_module_name = clean_module_name[: MODULE_COLUMN_WIDTH - 1] + "+"
    line = "%s [%-14s] %s" % (
        _level_prefix(level),
        clean_module_name,
        clean_message,
    )
    if color_enabled:
        color_code = _level_color(level)
        if color_code is not None:
            line = "\x1b[%sm%s\x1b[0m" % (color_code, line)
    return line + "\r\n"
