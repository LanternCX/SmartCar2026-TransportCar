"""启动阶段日志工具

@file src/utils/startup_log.py
@brief 提供统一格式的启动日志打印函数
"""


def startup_log(stage: str, detail: str = "") -> str:
    """打印统一格式的启动日志并返回文本

    @brief 在启动初始化阶段输出格式统一的调试信息

    @param stage 启动阶段标识符 (如 "IMU", "Motor", "Vision")
    @param detail 阶段的详细说明 (可选, 默认为空)

    @return 完整的日志消息字符串, 格式为 "[boot] stage: detail"
    """
    message = "[boot] %s" % stage
    if detail:
        message = "%s: %s" % (message, detail)
    print(message)
    return message
