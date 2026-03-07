"""运行时诊断输出辅助函数."""


def _sanitize_text(value):
    """将字符串值清理为单行串口安全文本."""
    text = str(value)
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = text.replace(",", ";")
    return text


def format_snapshot_value(value):
    """格式化单个诊断字段值."""
    if value is None:
        return "none"
    return _sanitize_text(value)


def format_query_response(token, snapshot):
    """将快照字典编码为查询响应行."""
    parts = []
    for key, value in snapshot.items():
        parts.append("%s:%s" % (key, format_snapshot_value(value)))
    return "?%s=%s\r\n" % (token, ",".join(parts))


def format_observe_line(token, snapshot):
    """将快照字典编码为设备观测输出行."""
    parts = []
    for key, value in snapshot.items():
        parts.append("%s=%s" % (key, format_snapshot_value(value)))
    return "OBSERVE %s %s" % (token, " ".join(parts))
