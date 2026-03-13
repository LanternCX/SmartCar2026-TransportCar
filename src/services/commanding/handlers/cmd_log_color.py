"""log_color 日志颜色开关指令处理器."""

from services.commanding.router import router


@router.command("log_color", value_type="raw")
def handle(ctx, value):
    """更新日志颜色输出开关."""
    normalized = str(value).strip()
    if normalized not in ("0", "1"):
        raise ValueError("invalid log color: %s" % value)
    ctx.logger_manager.set_color_enabled(normalized == "1")
