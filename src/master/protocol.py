"""主车与辅车之间的协议适配层

@file src/master/protocol.py

负责收口主车发给辅车的控制报文格式, 以及辅车状态回包的解析入口。
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


def build_follow_command(seq, valid, dx, dy):
    """构造主车到辅车的高频跟随报文

    @brief 按约定格式生成 `follow=1,...` 文本
    @param seq 递增控制序号
    @param valid 当前拍是否有有效目标
    @param dx 车体系横向位置式控制量
    @param dy 车体系纵向位置式控制量
    @return str
    """

    return "follow=1,seq=%d,valid=%d,dx=%.3f,dy=%.3f" % (
        int(seq),
        1 if int(valid) else 0,
        float(dx),
        float(dy),
    )


def parse_assistant_state(line):
    """解析辅车状态回包文本

    @brief 只接受带 `state=1` 头标记的报文, 并把关键底座状态转成主车可直接消费的字典。
    @param line UART 读到的一行文本
    @return dict | None
    """

    payload = {}
    for item in str(line).strip().split(","):
        field = item.strip()
        if not field:
            continue
        if "=" not in field:
            return None
        key, value = field.split("=", 1)
        payload[key.strip().lower()] = value.strip()
    if payload.get("state") != "1":
        return None
    return {
        "state_label": str(payload.get("state_label", "IDLE")).upper(),
        "last_seq": int(payload.get("last_seq", 0) or 0),
        "follow_active": 1 if int(payload.get("follow_active", 0) or 0) else 0,
        "heading_deg": float(payload.get("heading_deg", 0.0) or 0.0),
        "target_heading_deg": float(payload.get("target_heading_deg", 0.0) or 0.0),
        "yaw_rate_deg_s": float(payload.get("yaw_rate_deg_s", 0.0) or 0.0),
        "odom_x": float(payload.get("odom_x", 0.0) or 0.0),
        "odom_y": float(payload.get("odom_y", 0.0) or 0.0),
        "base_ok": 1 if int(payload.get("base_ok", 0) or 0) else 0,
    }
