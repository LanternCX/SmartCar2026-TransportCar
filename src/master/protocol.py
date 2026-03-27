"""主车到辅车的协议文本构造

@file src/master/protocol.py
"""


def build_move_command(dx, dy, dtheta):
    """构造辅车运动命令

    @brief 按文本协议格式生成 `MOVE` 命令
    @param dx 右向增量
    @param dy 前向增量
    @param dtheta 顺时针角增量
    @return str
    """

    return "MOVE %.3f %.3f %.3f" % (float(dx), float(dy), float(dtheta))


def build_hold_command():
    """构造辅车保持命令

    @brief 按文本协议格式生成 `HOLD` 命令
    @return str
    """

    return "HOLD"


def build_follow_command(seq, valid, dx, dy, d_angle):
    """构造主车到辅车的高频跟随报文

    @brief 按约定格式生成 `follow=1,...` 文本
    @param seq 递增控制序号
    @param valid 当前拍是否有有效目标
    @param dx 车体系横向位置式控制量
    @param dy 车体系纵向位置式控制量
    @param d_angle 角度位置式控制量
    @return str
    """

    return "follow=1,seq=%d,valid=%d,dx=%.3f,dy=%.3f,d_angle=%.3f" % (
        int(seq),
        1 if int(valid) else 0,
        float(dx),
        float(dy),
        float(d_angle),
    )
