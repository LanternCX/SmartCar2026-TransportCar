"""主车最小状态输出.

@file src/master/status.py
"""


def render_status(last_target, assistant_command):
    """生成主车最小状态文本

    @brief 只保留主车调试最小必要信息
    @param last_target 最近主车目标
    @param assistant_command 最近辅车命令
    @return str
    """

    kind = "none" if last_target is None else str(last_target.get("kind", "none"))
    return "STATUS self=%s assistant=%s" % (kind, str(assistant_command))
