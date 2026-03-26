"""主车到辅车的最小协议构造.

@file src/master/protocol.py
"""


def build_move_command(dx, dy, dtheta):
    """构造辅车运动命令

    @brief 以最小运动级协议输出 MOVE 文本
    @param dx 右向增量
    @param dy 前向增量
    @param dtheta 顺时针角增量
    @return str
    """

    return "MOVE %.3f %.3f %.3f" % (float(dx), float(dy), float(dtheta))


def build_hold_command():
    """构造辅车保持命令

    @brief 输出最小 HOLD 文本
    @return str
    """

    return "HOLD"
