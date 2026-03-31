"""辅车启动入口

@file src/assistant/main.py
"""

try:
    from assistant.app import AssistantRuntimeLoop, build_hw_bundle
except ImportError:
    from app import AssistantRuntimeLoop, build_hw_bundle


def main():
    """创建辅车运行循环入口对象

    @brief 为启动脚本提供辅车主线运行循环
    @return AssistantRuntimeLoop
    """

    hw_bundle = build_hw_bundle()
    loop_bundle = {"uart3": hw_bundle["uart"]["uart3"], "motors": hw_bundle["motors"]}
    return AssistantRuntimeLoop(loop_bundle)
