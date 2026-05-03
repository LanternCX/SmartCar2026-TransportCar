"""
@file src/protocol/packet.py
@brief 串口短包协议解析与格式化工具
"""

import math


SEQ_MIN = 0
SEQ_MAX = 255
_SEQ_RING_SIZE = 256
_SEQ_HALF_RING = 128


def _split_fields(line):
    """
    @brief 拆分短包字段并过滤空字段

    @param line 原始输入行
    @return 字段列表, 输入无效时返回 None
    """

    text = line.strip()
    if not text:
        return None
    fields = [item.strip() for item in text.split(",")]
    if not fields or not fields[0]:
        return None
    for field in fields:
        if field == "":
            return None
    return fields


def _parse_float(text):
    """
    @brief 解析有限浮点数

    @param text 数值文本
    @return 浮点数, 输入无效时返回 None
    """

    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _parse_int(text):
    """
    @brief 解析严格整数字段

    @param text 数值文本
    @return 整数, 输入无效时返回 None
    """

    try:
        value = int(text)
    except ValueError:
        return None
    if str(value) != text.strip():
        return None
    return value


def _parse_u8(text):
    """
    @brief 解析 0..255 范围内的整数字段

    @param text 数值文本
    @return 整数, 输入无效时返回 None
    """

    value = _parse_int(text)
    if value is None or value < SEQ_MIN or value > SEQ_MAX:
        return None
    return value


def parse_short_packet(line):
    """
    @brief 解析一行短包协议

    @param line 输入行文本
    @return 解析后的字段字典, 非法输入返回 None
    """

    fields = _split_fields(line)
    if fields is None:
        return None

    packet_type = fields[0].lower()
    if packet_type == "v":
        return _parse_velocity(fields)
    if packet_type == "s":
        return _parse_state_sync(fields)
    if packet_type == "a":
        return _parse_ack(fields)
    if packet_type == "r":
        return _parse_event(fields)
    if packet_type == "o":
        return _parse_observation(fields)
    return None


def _parse_velocity(fields):
    """
    @brief 解析速度短包字段

    @param fields 已拆分字段列表
    @return 速度短包字典, 输入无效时返回 None
    """

    if len(fields) != 3 and len(fields) != 4:
        return None
    vx = _parse_float(fields[1])
    vy = _parse_float(fields[2])
    if vx is None or vy is None:
        return None
    has_omega = len(fields) == 4
    omega = 0.0
    if has_omega:
        omega = _parse_float(fields[3])
        if omega is None:
            return None
    return {
        "type": "v",
        "vx": vx,
        "vy": vy,
        "omega": omega,
        "has_omega": has_omega,
    }


def _parse_state_sync(fields):
    """
    @brief 解析状态同步短包字段

    @param fields 已拆分字段列表
    @return 状态同步短包字典, 输入无效时返回 None
    """

    if len(fields) != 6:
        return None
    reliable_seq = _parse_u8(fields[1])
    context_id = _parse_u8(fields[2])
    state = _parse_u8(fields[3])
    target = _parse_u8(fields[4])
    arg = _parse_int(fields[5])
    if (
        reliable_seq is None
        or context_id is None
        or state is None
        or target is None
        or arg is None
    ):
        return None
    return {
        "type": "s",
        "reliable_seq": reliable_seq,
        "context_id": context_id,
        "state": state,
        "target": target,
        "arg": arg,
    }


def _parse_ack(fields):
    """
    @brief 解析确认短包字段

    @param fields 已拆分字段列表
    @return 确认短包字典, 输入无效时返回 None
    """

    if len(fields) != 2:
        return None
    reliable_seq = _parse_u8(fields[1])
    if reliable_seq is None:
        return None
    return {"type": "a", "reliable_seq": reliable_seq}


def _parse_event(fields):
    """
    @brief 解析事件回报短包字段

    @param fields 已拆分字段列表
    @return 事件回报短包字典, 输入无效时返回 None
    """

    if len(fields) != 5:
        return None
    reliable_seq = _parse_u8(fields[1])
    context_id = _parse_u8(fields[2])
    event = _parse_u8(fields[3])
    value = _parse_int(fields[4])
    if reliable_seq is None or context_id is None or event is None or value is None:
        return None
    return {
        "type": "r",
        "reliable_seq": reliable_seq,
        "context_id": context_id,
        "event": event,
        "value": value,
    }


def _parse_observation(fields):
    """
    @brief 解析观测短包字段

    @param fields 已拆分字段列表
    @return 观测短包字典, 输入无效时返回 None
    """

    if len(fields) != 5:
        return None
    context_id = _parse_u8(fields[1])
    x = _parse_float(fields[2])
    y = _parse_float(fields[3])
    value = _parse_float(fields[4])
    if context_id is None or x is None or y is None or value is None:
        return None
    return {"type": "o", "context_id": context_id, "x": x, "y": y, "value": value}


def _require_u8(value):
    """
    @brief 校验并返回 0..255 范围内的整数

    @param value 待校验的数值
    @return 0..255 范围内的整数
    @raises ValueError 数值超出范围
    """

    value = int(value)
    if value < SEQ_MIN or value > SEQ_MAX:
        raise ValueError("u8 out of range")
    return value


def format_velocity_packet(vx, vy, omega=None):
    """
    @brief 格式化速度短包

    @param vx 车体系 x 方向速度或速度修正量
    @param vy 车体系 y 方向速度或速度修正量
    @param omega 车体系角速度, 为 None 时不输出该字段
    @return 速度短包文本
    """

    if omega is None:
        return "v,%s,%s" % (float(vx), float(vy))
    return "v,%s,%s,%s" % (float(vx), float(vy), float(omega))


def format_state_sync_packet(reliable_seq, context_id, state, target, arg):
    """
    @brief 格式化主车视觉 hook 状态同步短包

    @param reliable_seq 可靠包序号
    @param context_id 业务上下文编号
    @param state 状态编号
    @param target 目标编号
    @param arg 状态参数或 hook 配置编号
    @return 状态同步短包文本
    """

    return "s,%d,%d,%d,%d,%d" % (
        _require_u8(reliable_seq),
        _require_u8(context_id),
        _require_u8(state),
        _require_u8(target),
        int(arg),
    )


def format_ack_packet(reliable_seq):
    """
    @brief 格式化确认短包

    @param reliable_seq 被确认的可靠包序号
    @return 确认短包文本
    """

    return "a,%d" % _require_u8(reliable_seq)


def format_observation_packet(context_id, x, y, value):
    """
    @brief 格式化观测短包

    @param context_id 业务上下文编号
    @param x 观测 x 分量
    @param y 观测 y 分量
    @param value 观测附加值
    @return 观测短包文本
    """

    return "o,%d,%s,%s,%s" % (
        _require_u8(context_id),
        float(x),
        float(y),
        float(value),
    )


def format_event_packet(reliable_seq, context_id, event, value):
    """
    @brief 格式化事件回报短包

    @param reliable_seq 可靠包序号
    @param context_id 业务上下文编号
    @param event 事件编号
    @param value 事件附加值
    @return 事件回报短包文本
    """

    return "r,%d,%d,%d,%d" % (
        _require_u8(reliable_seq),
        _require_u8(context_id),
        _require_u8(event),
        int(value),
    )


def is_later_ring_value(value, last_value):
    """
    @brief 按 0..255 环形编号判断 value 是否晚于 last_value

    @param value 待判断的编号
    @param last_value 已记录的编号, None 表示没有历史编号
    @return value 是否晚于 last_value
    """

    value = _require_u8(value)
    if last_value is None:
        return True
    last_value = _require_u8(last_value)
    diff = (value - last_value) % _SEQ_RING_SIZE
    return diff != 0 and diff < _SEQ_HALF_RING


def is_newer_seq(value, last_value):
    """
    @brief 按 0..255 环形序号判断 value 是否晚于 last_value

    @param value 待判断的序号
    @param last_value 已记录的序号, None 表示没有历史序号
    @return value 是否晚于 last_value
    """

    return is_later_ring_value(value, last_value)
