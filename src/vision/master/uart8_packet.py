"""主车 UART8 短包解析工具

@file src/vision/master/uart8_packet.py
"""

from protocol.packet import _parse_int, _parse_u8, _split_fields


def parse_short_packet(line):
    """解析主车 UART8 短包

    @param line 输入行文本
    @return 解析后的字段字典, 非法输入返回 None
    """

    fields = _split_fields(line)
    if fields is None:
        return None

    packet_type = fields[0].lower()
    if packet_type == "a":
        return _parse_ack(fields)
    if packet_type == "r":
        return _parse_event(fields)
    return None


def format_turn_packet():
    """格式化 UART8 半双工轮转短包"""

    return "t"


def _parse_ack(fields):
    """解析主车 UART8 确认短包

    @param fields 已拆分字段列表
    @return 确认短包字典, 输入无效时返回 None
    """

    if len(fields) != 2:
        return None
    seq = _parse_u8(fields[1])
    if seq is None:
        return None
    return {"type": "a", "seq": seq}


def _parse_event(fields):
    """解析主车 UART8 事件回报短包

    @param fields 已拆分字段列表
    @return 事件回报短包字典, 输入无效时返回 None
    """

    if len(fields) != 4:
        return None
    seq = _parse_u8(fields[1])
    event = _parse_u8(fields[2])
    value = _parse_int(fields[3])
    if seq is None or event is None or value is None:
        return None
    return {"type": "r", "seq": seq, "event": event, "value": value}
