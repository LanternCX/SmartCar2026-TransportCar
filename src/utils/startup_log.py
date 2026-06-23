"""板端日志工具

@file src/utils/startup_log.py
@brief 提供统一格式的日志打印函数
"""


import time


cnt = 0


def _now_ms() -> int:
    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def log(stage: str, detail: str = "") -> str:
    """打印统一格式的日志并返回文本

    @brief 输出格式统一的调试信息

    @param stage 阶段标识符 (如 "IMU", "Motor", "Vision")
    @param detail 阶段的详细说明 (可选, 默认为空)

    @return 完整的日志消息字符串, 格式为 "cnt timestamp_ms stage: detail"
    """
    global cnt

    message = "%d %dms %s" % (cnt, _now_ms(), stage)
    if detail:
        message = "%s: %s" % (message, detail)
    print(message)
    cnt += 1
    return message


def write_exception_trace(output, exc: Exception) -> None:
    """输出完整异常调用链."""

    import sys

    print_exception = getattr(sys, "print_exception", None)
    if print_exception is not None:
        if output is None:
            print_exception(exc)
            return
        print_exception(exc, output)
        return

    import traceback

    traceback.print_exception(type(exc), exc, exc.__traceback__, file=output)


def log_exception(stage: str, detail: str, exc: Exception) -> str:
    """打印异常摘要和完整调用链."""

    message = log(stage, detail)
    print("%s: traceback start" % stage)
    write_exception_trace(None, exc)
    print("%s: traceback end" % stage)
    return message
