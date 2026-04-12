"""从辅车运行时读取内部状态, 向下游协议层提供稳定的最小状态标签和回包内容。

它位于主链状态出口, 对外职责是屏蔽内部细节, 只暴露主车轮询需要的状态结果。

@file src/assistant/status.py
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)


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

    @brief 这里只读取状态对象并生成对外回包, 不回写运行时内部状态
    @param state 当前辅车运行时状态
    @return str
    """

    if _USE_DIRECT_IMPORTS:
        from protocol import render_state_line
    else:
        from .protocol import render_state_line

    # 对外只暴露协议约定字段, 避免运行时内部标签直接外溢
    return render_state_line(state, state_label=_normalize_state_label(state))
