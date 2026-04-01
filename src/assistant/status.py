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


def _normalize_state_label(state):
    """将内部状态收口为对外最小状态标签

    @brief 对外只暴露 `IDLE`、`BUSY`、`TIMEOUT`
    @param state 当前辅车状态
    @return str
    """

    if bool(state.timeout) or state.last_error == "timeout_stop":
        return "TIMEOUT"
    if bool(state.follow_active):
        return "BUSY"
    label = str(getattr(state, "state_label", "")).upper()
    if label in ("IDLE", "BUSY", "TIMEOUT"):
        return label
    return "IDLE"


def render_state(state):
    """序列化辅车状态回包

    @brief 按协议格式生成单行 `STATE` 文本
    @param state 当前辅车状态
    @return str
    """

    state.state_label = _normalize_state_label(state)
    from .protocol import render_state_line

    return render_state_line(state)
