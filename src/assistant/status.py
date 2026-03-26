"""辅车最小状态结构与回报

@file src/assistant/status.py
"""


class AssistantState:
    """辅车最小执行状态

    @brief 只保留第一版执行闭环需要的最小字段
    """

    def __init__(self):
        self.armed = False
        self.busy = False
        self.last_cmd = "idle"
        self.odom = [0.0, 0.0]
        self.heading_deg = 0.0
        self.velocity_command = (0.0, 0.0, 0.0)
        self.last_error = ""


def render_state(state):
    """序列化最小状态回包

    @brief 生成单行 `STATE` 文本
    @param state 当前辅车状态
    @return str
    """

    return "STATE armed=%d busy=%d last_cmd=%s odom=%.3f,%.3f heading=%.3f" % (
        1 if state.armed else 0,
        1 if state.busy else 0,
        state.last_cmd,
        state.odom[0],
        state.odom[1],
        state.heading_deg,
    )
