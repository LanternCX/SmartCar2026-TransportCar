"""辅车状态结构与回包

@file src/assistant/status.py
"""


class AssistantState:
    """保存辅车执行阶段的核心状态

    @brief 供运行时更新和状态回包复用
    """

    def __init__(self):
        # 跟随状态、里程和最近一次错误统一保存在状态对象中
        self.follow_active = False
        self.last_seq = 0
        self.odom = [0.0, 0.0]
        self.heading_deg = 0.0
        self.velocity_command = (0.0, 0.0, 0.0)
        self.timeout = False
        self.last_error = ""


def render_state(state):
    """序列化辅车状态回包

    @brief 按协议格式生成单行 `STATE` 文本
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
