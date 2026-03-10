"""log_color 运行时日志颜色开关指令处理器."""

from typing import cast

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_color", value_type="raw")
def handle(ctx: object, value: CommandValue) -> None:
    """更新日志颜色输出开关."""
    local_ctx = cast(LogCommandContext, ctx)
    normalized = str(value).strip()
    if normalized not in ("0", "1"):
        raise ValueError("invalid log color: %s" % value)
    local_ctx.logger_manager.set_color_enabled(normalized == "1")
