"""启动阶段日志工具.

@file src/utils/startup_log.py
"""


def startup_log(stage: str, detail: str = "") -> str:
    """打印统一格式的启动日志并返回文本."""

    message = "[boot] %s" % stage
    if detail:
        message = "%s: %s" % (message, detail)
    print(message)
    return message
