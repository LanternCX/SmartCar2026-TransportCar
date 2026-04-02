"""辅车跨周期状态入口.

@file src/assistant/state/__init__.py
"""


class AssistantState:
    """保存辅车跨周期最小运行状态.

    @brief 这里只承载长期状态字段, 由运行时 owner 持有并按周期更新。
    """

    def __init__(self):
        self.follow_active = False
        self.state_label = "IDLE"
        self.last_seq = 0
        self.odom = [0.0, 0.0]
        self.heading_deg = 0.0
        self.target_heading_deg = 0.0
        self.yaw_rate_deg_s = 0.0
        self.base_ok = False
        self.velocity_command = (0.0, 0.0, 0.0)
        self.timeout = False
        self.last_error = ""
