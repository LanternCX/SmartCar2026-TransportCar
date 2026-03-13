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


def format_pos_query_response(snapshot):
    """将位置快照编码为位置查询响应行."""
    return "?pos=%.3f,%.3f,%.2f\r\n" % (
        float(snapshot.get("x", 0.0)),
        float(snapshot.get("y", 0.0)),
        float(snapshot.get("heading_deg", 0.0)),
    )


def format_lock_query_response(snapshot):
    """将锁定快照编码为锁定查询响应行."""
    return "?lock=%d\r\n" % int(snapshot.get("locked", 0))


def format_log_query_response(snapshot):
    """将日志快照编码为日志查询响应行."""
    return "?log=profile:%s,level:%s,filter:%s,color:%d,modules:%s\r\n" % (
        format_snapshot_value(snapshot.get("profile", "run")),
        format_snapshot_value(snapshot.get("level", "info")),
        format_snapshot_value(snapshot.get("filter", "off")),
        int(snapshot.get("color", 0)),
        format_snapshot_value(snapshot.get("modules", "none")),
    )


def build_query_response_from_facade(token, facade):
    """通过 diagnostics facade 构造指定查询响应文本."""
    if token == "health":
        return format_query_response(token, facade.build_health_snapshot())
    if token == "tick":
        return format_query_response(token, facade.build_tick_snapshot())
    if token == "imu":
        return format_query_response(token, facade.build_imu_snapshot())
    if token == "enc":
        return format_query_response(token, facade.build_encoder_snapshot())
    if token == "motor":
        return format_query_response(token, facade.build_motor_snapshot())
    if token == "vision":
        return format_query_response(token, facade.build_vision_snapshot())
    if token == "pos":
        return format_pos_query_response(facade.build_pos_snapshot())
    if token == "lock":
        return format_lock_query_response(facade.build_lock_snapshot())
    if token == "log":
        return format_log_query_response(facade.build_log_snapshot())
    raise ValueError("unsupported diagnostic query: %s" % token)


def format_observe_line(token, snapshot):
    """将快照字典编码为设备观测输出行."""
    parts = []
    for key, value in snapshot.items():
        parts.append("%s=%s" % (key, format_snapshot_value(value)))
    return "OBSERVE %s %s" % (token, " ".join(parts))
