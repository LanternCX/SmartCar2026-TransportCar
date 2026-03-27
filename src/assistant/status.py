"""辅车最小状态结构与回报

@file src/assistant/status.py
"""


class AssistantState:
    """辅车最小执行状态

    @brief 只保留第一版执行闭环需要的最小字段
    """

    def __init__(self):
        self.follow_active = False
        self.last_seq = 0
        self.odom = [0.0, 0.0]
        self.heading_deg = 0.0
        self.velocity_command = (0.0, 0.0, 0.0)
        self.timeout = False
        self.last_error = ""


def render_state(state):
    """序列化最小状态回包

    @brief 生成单行 `STATE` 文本
    @param state 当前辅车状态
    @return str
    """

    return (
        "state=1,follow_active=%d,last_seq=%d,odom_x=%.3f,odom_y=%.3f,heading=%.3f,timeout=%d"
        % (
            1 if state.follow_active else 0,
            int(state.last_seq),
            state.odom[0],
            state.odom[1],
            state.heading_deg,
            1 if state.timeout else 0,
        )
    )
