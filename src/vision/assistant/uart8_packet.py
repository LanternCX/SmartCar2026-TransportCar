"""辅车 UART8 短包解析工具

@file src/vision/assistant/uart8_packet.py
"""

from protocol.packet import _parse_int, _parse_u8, _split_fields
from protocol.packet import is_newer_seq


def parse_short_packet(line):
    """解析辅车侧短包

    @param line 输入行文本
    @return 解析后的字段字典, 非法输入返回 None
    """

    fields = _split_fields(line)
    if fields is None:
        return None

    packet_type = fields[0].lower()
    if packet_type == "s":
        return _parse_state_sync(fields)
    if packet_type == "a":
        return _parse_ack(fields)
    if packet_type == "r":
        return _parse_event(fields)
    return None


def _parse_state_sync(fields):
    """解析辅车状态同步短包

    @param fields 已拆分字段列表
    @return 解析后的字段字典, 非法输入返回 None
    """

    if len(fields) != 5:
        return None

    seq = _parse_u8(fields[1])
    state = _parse_u8(fields[2])
    target = _parse_u8(fields[3])
    arg = _parse_int(fields[4])
    if seq is None or state is None or target is None or arg is None:
        return None
    return {"type": "s", "seq": seq, "state": state, "target": target, "arg": arg}


def _parse_ack(fields):
    """解析辅车确认短包

    @param fields 已拆分字段列表
    @return 解析后的字段字典, 非法输入返回 None
    """

    if len(fields) != 2:
        return None
    seq = _parse_u8(fields[1])
    if seq is None:
        return None
    return {"type": "a", "seq": seq}


def _parse_event(fields):
    """解析辅车事件回报短包

    @param fields 已拆分字段列表
    @return 解析后的字段字典, 非法输入返回 None
    """

    if len(fields) != 4:
        return None
    seq = _parse_u8(fields[1])
    event = _parse_u8(fields[2])
    value = _parse_int(fields[3])
    if seq is None or event is None or value is None:
        return None
    return {"type": "r", "seq": seq, "event": event, "value": value}


def format_state_sync_packet(seq, state, target, arg):
    """格式化辅车本地视觉状态同步短包

    @param seq 状态同步序号
    @param state 辅车子状态
    @param target 辅车子目标
    @param arg 辅车状态参数
    @return 状态同步短包文本
    """

    return "s,%d,%d,%d,%d" % (
        _require_u8(seq),
        _require_u8(state),
        _require_u8(target),
        int(arg),
    )


def format_ack_packet(seq):
    """格式化辅车确认短包

    @param seq 被确认的可靠序号
    @return 确认短包文本
    """

    return "a,%d" % _require_u8(seq)


def format_event_packet(seq, event, value):
    """格式化辅车事件回报短包

    @param seq 可靠序号
    @param event 事件编号
    @param value 事件附加值
    @return 事件回报短包文本
    """

    return "r,%d,%d,%d" % (_require_u8(seq), _require_u8(event), int(value))


def _require_u8(value):
    """校验并返回 0..255 范围内的整数

    @param value 待校验数值
    @return 0..255 范围内的整数
    @raises ValueError 数值超出范围
    """

    value = int(value)
    if value < 0 or value > 255:
        raise ValueError("u8 out of range")
    return value
