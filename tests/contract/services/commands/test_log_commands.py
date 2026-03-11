"""运行时日志命令与查询的契约测试."""

import pytest

from services.commands import (
    cmd_log_color,
    cmd_log_filter,
    cmd_log_level,
    cmd_log_modules,
    cmd_log_profile,
    cmd_log_reset,
    query_log,
)
from tests.fakes.fake_context import FakeCommandContext


pytestmark = pytest.mark.contract


def test_log_profile_run_applies_runtime_defaults() -> None:
    ctx = FakeCommandContext()

    cmd_log_profile.handle(ctx, "run")

    assert ctx.logger_manager.profile_name == "RUN"
    assert ctx.logger_manager.level_name == "INFO"
    assert ctx.logger_manager.filter_mode == "off"


def test_log_profile_diag_switches_to_debug_profile() -> None:
    ctx = FakeCommandContext()

    cmd_log_profile.handle(ctx, "diag")

    assert ctx.logger_manager.profile_name == "DIAG"
    assert ctx.logger_manager.level_name == "DEBUG"
    assert ctx.logger_manager.filter_mode == "off"


def test_log_level_command_updates_runtime_logger() -> None:
    ctx = FakeCommandContext()

    cmd_log_level.handle(ctx, "debug")

    assert ctx.logger_manager.level_name == "DEBUG"


def test_log_level_command_marks_profile_custom_after_effective_override() -> None:
    ctx = FakeCommandContext()
    cmd_log_profile.handle(ctx, "diag")

    cmd_log_level.handle(ctx, "warn")

    assert ctx.logger_manager.profile_name == "CUSTOM"


def test_log_level_command_keeps_profile_when_override_is_noop() -> None:
    ctx = FakeCommandContext()
    cmd_log_profile.handle(ctx, "diag")

    cmd_log_level.handle(ctx, "debug")

    assert ctx.logger_manager.profile_name == "DIAG"


def test_log_filter_command_updates_runtime_mode() -> None:
    ctx = FakeCommandContext()

    cmd_log_filter.handle(ctx, "whitelist")

    assert ctx.logger_manager.filter_mode == "whitelist"


def test_log_filter_command_marks_profile_custom_after_effective_override() -> None:
    ctx = FakeCommandContext()
    cmd_log_profile.handle(ctx, "diag")

    cmd_log_filter.handle(ctx, "blacklist")

    assert ctx.logger_manager.profile_name == "CUSTOM"


def test_log_modules_command_splits_pipe_delimited_modules() -> None:
    ctx = FakeCommandContext()

    cmd_log_modules.handle(ctx, "vision|control.yaw")

    assert ctx.logger_manager.filter_modules == ("vision", "control.yaw")


def test_log_modules_command_supports_none_keyword() -> None:
    ctx = FakeCommandContext()

    cmd_log_modules.handle(ctx, "none")

    assert ctx.logger_manager.filter_modules == ()


def test_log_modules_command_treats_whitespace_only_as_empty() -> None:
    ctx = FakeCommandContext()
    ctx.logger_manager.set_filter_modules(("vision",))

    cmd_log_modules.handle(ctx, "   ")

    assert ctx.logger_manager.filter_modules == ()


def test_log_color_command_parses_boolean_flag() -> None:
    ctx = FakeCommandContext()

    cmd_log_color.handle(ctx, "1")

    assert ctx.logger_manager.color_enabled is True


def test_log_color_command_rejects_invalid_flag() -> None:
    ctx = FakeCommandContext()

    with pytest.raises(ValueError, match="invalid log color"):
        cmd_log_color.handle(ctx, "2")


def test_log_profile_command_rejects_invalid_value() -> None:
    ctx = FakeCommandContext()

    with pytest.raises(ValueError, match="invalid log profile"):
        cmd_log_profile.handle(ctx, "fast")


def test_log_level_command_rejects_invalid_value() -> None:
    ctx = FakeCommandContext()

    with pytest.raises(ValueError, match="invalid log level"):
        cmd_log_level.handle(ctx, "verbose")


def test_log_filter_command_rejects_invalid_value() -> None:
    ctx = FakeCommandContext()

    with pytest.raises(ValueError, match="invalid filter_mode"):
        cmd_log_filter.handle(ctx, "allow")


def test_log_reset_restores_runtime_defaults() -> None:
    ctx = FakeCommandContext()
    ctx.logger_manager.set_profile("DIAG")
    ctx.logger_manager.set_filter_mode("blacklist")
    ctx.logger_manager.set_filter_modules(("vision",))
    ctx.logger_manager.set_color_enabled(True)

    cmd_log_reset.handle(ctx, True)

    assert ctx.logger_manager.profile_name == "RUN"
    assert ctx.logger_manager.level_name == "INFO"
    assert ctx.logger_manager.filter_mode == "off"
    assert ctx.logger_manager.filter_modules == ()
    assert ctx.logger_manager.color_enabled is False


def test_query_log_formats_current_runtime_config_with_custom_profile() -> None:
    ctx = FakeCommandContext()
    ctx.logger_manager.set_profile("DIAG")
    ctx.logger_manager.set_level_name("DEBUG")
    ctx.logger_manager.set_filter_mode("whitelist")
    ctx.logger_manager.set_filter_modules(("vision", "control.yaw"))
    ctx.logger_manager.set_color_enabled(True)

    query_log.handle(ctx)

    assert ctx.uart6.messages == [
        "?log=profile:custom,level:debug,filter:whitelist,color:1,modules:vision|control.yaw\r\n"
    ]


def test_query_log_reports_custom_profile_after_effective_manual_override() -> None:
    ctx = FakeCommandContext()

    cmd_log_profile.handle(ctx, "diag")
    cmd_log_level.handle(ctx, "warn")

    query_log.handle(ctx)

    assert ctx.uart6.messages == [
        "?log=profile:custom,level:warn,filter:off,color:0,modules:none\r\n"
    ]


def test_query_log_formats_empty_modules_as_none() -> None:
    ctx = FakeCommandContext()

    query_log.handle(ctx)

    assert ctx.uart6.messages == [
        "?log=profile:run,level:info,filter:off,color:0,modules:none\r\n"
    ]
