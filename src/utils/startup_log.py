"""板端日志工具

@file src/utils/startup_log.py
@brief 提供统一格式的日志打印函数
"""


cnt = 0


def log(stage: str, detail: str = "") -> str:
    """打印统一格式的日志并返回文本

    @brief 输出格式统一的调试信息

    @param stage 阶段标识符 (如 "IMU", "Motor", "Vision")
    @param detail 阶段的详细说明 (可选, 默认为空)

    @return 完整的日志消息字符串, 格式为 "cnt stage: detail"
    """
    global cnt

    message = "%d %s" % (cnt, stage)
    if detail:
        message = "%s: %s" % (message, detail)
    print(message)
    cnt += 1
    return message
