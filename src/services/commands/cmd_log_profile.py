"""log_profile 运行时日志档位指令处理器."""

from typing import cast

from services.command_router import CommandValue, router
from diagnostics.manager import LogCommandContext


@router.command("log_profile", value_type="raw")
def handle(ctx: object, value: CommandValue) -> None:
    """更新日志预设档位."""
    local_ctx = cast(LogCommandContext, ctx)
    local_ctx.logger_manager.set_profile(str(value))
