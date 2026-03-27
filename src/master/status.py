"""主车状态文本输出

@file src/master/status.py
"""


def render_status(last_target, assistant_command):
    """生成主车状态文本

    @brief 输出主车目标类型和最近一次辅车命令
    @param last_target 最近主车目标
    @param assistant_command 最近辅车命令
    @return str
    """

    kind = "none" if last_target is None else str(last_target.get("kind", "none"))
    return "STATUS self=%s assistant=%s" % (kind, str(assistant_command))
