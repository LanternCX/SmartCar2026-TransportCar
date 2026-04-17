"""辅车角色运行时诊断快照

@file src/vision/assistant/diagnostics.py
"""


def build_follow_snapshot(
    transport_command: dict,
    uart8_status: str,
    vision_snapshot: dict,
    vision_status: str,
    last_error_text: str,
) -> dict:
    """组织辅车角色层最小诊断快照

    @brief 只导出当前共享底盘命令状态和本地观测状态, 不再暴露旧的融合语义
    """

    state = "idle"
    if uart8_status == "active" or vision_status == "active":
        state = "active"

    return {
        "state": state,
        "transport_command": transport_command,
        "uart8_input_status": uart8_status,
        "vision_input": vision_snapshot,
        "vision_input_status": vision_status,
        "last_error_text": last_error_text,
    }
