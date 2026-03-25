"""@brief 诊断 facade 的格式与字段辅助函数."""

HEALTH_SNAPSHOT_FIELDS = (
    "alive",
    "uptime_ms",
    "lock",
    "rear",
    "oom_count",
    "oom_stage",
    "last_err",
    "vision_state",
)

TICK_SNAPSHOT_FIELDS = (
    "count",
    "last_us",
    "max_us",
    "avg_us",
    "overrun",
)

VISION_SNAPSHOT_FIELDS = (
    "state",
    "obs_age_ms",
    "obs_left",
    "obs_top",
    "obs_right",
    "obs_bottom",
    "obs_center_x",
    "obs_center_y",
    "target_x",
    "target_y",
    "target_angle",
)


def format_query_value(value):
    """@brief 将查询值格式化为单行串口安全文本.

    @param value 任意待格式化值
    @return str 去除换行并替换逗号后的文本
    """
    if value is None:
        return "none"
    text = str(value)
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = text.replace(",", ";")
    return text


def select_snapshot_fields(snapshot, fields):
    """@brief 按固定字段顺序裁剪快照.

    @param snapshot 原始快照字典
    @param fields 期望保留的字段顺序
    @return dict 仅包含目标字段的有序快照
    """
    ordered_snapshot = {}
    for name in fields:
        ordered_snapshot[name] = snapshot.get(name)
    return ordered_snapshot
