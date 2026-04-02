"""辅车最小状态回包入口

@file src/assistant/status.py
"""


def _normalize_state_label(state):
    """将运行时状态收口为对外最小状态标签

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
    """序列化辅车最小状态回包

    @brief 这里只负责最小状态文本, 不持有长期状态 owner
    @param state 当前辅车运行时状态
    @return str
    """

    state.state_label = _normalize_state_label(state)
    from .protocol import render_state_line

    return render_state_line(state)
