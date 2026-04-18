"""辅车角色运行时诊断快照

@file src/vision/assistant/diagnostics.py
"""


def build_follow_snapshot(
    transport_command: dict,
    uart6_status: str,
    uart8_status: str,
    last_error_text: str,
) -> dict:
    """组织辅车角色层最小诊断快照

    @brief 只导出当前共享底盘命令状态和两路速度输入状态
    """

    state = "idle"
    if uart6_status == "active" or uart8_status == "active":
        state = "active"

    return {
        "state": state,
        "transport_command": transport_command,
        "uart6_input_status": uart6_status,
        "uart8_input_status": uart8_status,
        "last_error_text": last_error_text,
    }
