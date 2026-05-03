"""辅车角色运行时诊断快照

@file src/vision/assistant/diagnostics.py
"""


def build_follow_snapshot(
    assistant_state: int,
    transport_command: dict,
    uart6_status: str,
    uart8_status: str,
    uart6_velocity: dict,
    uart8_velocity: dict,
    last_error_text: str,
) -> dict:
    """组织辅车角色层最小诊断快照

    只导出当前共享底盘控制状态和两路速度输入状态

    @param assistant_state 辅车当前子状态
    @param transport_command 共享底盘控制状态
    @param uart6_status UART6 输入状态
    @param uart8_status UART8 输入状态
    @param uart6_velocity UART6 速度输入
    @param uart8_velocity UART8 速度输入
    @param last_error_text 最近错误文本
    @return 诊断快照字典
    """

    state = "idle"
    if uart6_status == "active" or uart8_status == "active":
        state = "active"

    return {
        "state": state,
        "assistant_state": int(assistant_state),
        "transport_command": transport_command,
        "uart6_input_status": uart6_status,
        "uart8_input_status": uart8_status,
        "uart6_velocity": uart6_velocity,
        "uart8_velocity": uart8_velocity,
        "last_error_text": last_error_text,
    }
