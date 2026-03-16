"""diagnostics 日志模块的单元测试."""

from typing import Any, cast

import pytest

import diagnostics.manager as manager_module
from diagnostics.sink import RingBufferSink
from diagnostics.manager import LOG_DEBUG, LOG_ERROR, LOG_INFO, LogManager


pytestmark = pytest.mark.unit


class FakeSink:
    """收集日志输出的假 sink."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text: str) -> None:
        self.lines.append(text)


class LegacySink:
    """仅提供 write 的旧 sink."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text: str) -> None:
        self.lines.append(text)


class MemoryErrorSink:
    """写出时触发 OOM 的假 sink."""

    def write(self, _text: str) -> None:
        raise MemoryError("sink oom")


class _ExplodingMessage:
    """若被转成字符串就立即失败的测试消息."""

    def __str__(self) -> str:
        raise AssertionError("message should not be formatted")


def test_log_manager_module_does_not_keep_legacy_runtime_tables() -> None:
    assert hasattr(manager_module, "LEVEL_NAME_TO_VALUE") is False
    assert hasattr(manager_module, "LEVEL_VALUE_TO_NAME") is False
    assert hasattr(manager_module, "VALID_FILTER_MODES") is False


def test_logger_is_cached_per_module_name() -> None:
    manager = LogManager()

    assert manager.get_logger("vision.state") is manager.get_logger("vision.state")


def test_filtered_debug_log_does_not_require_message_stringification() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=False, sinks=[sink])

    manager.get_logger("vision.state").debug(cast(Any, _ExplodingMessage()))

    assert sink.lines == []


def test_logger_blocks_debug_below_info_level() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=False, sinks=[sink])
    logger = manager.get_logger("vision.state")

    logger.debug("hidden")
    logger.info("shown")

    assert sink.lines == ["I [vision.state  ] shown\r\n"]


def test_logger_supports_whitelist_prefix_match() -> None:
    sink = FakeSink()
    manager = LogManager(
        level=LOG_DEBUG,
        color_enabled=False,
        filter_mode="whitelist",
        filter_modules=("vision",),
        sinks=[sink],
    )

    manager.get_logger("vision.state").debug("keep")
    manager.get_logger("control.yaw").debug("drop")

    assert sink.lines == ["D [vision.state  ] keep\r\n"]


def test_logger_supports_blacklist_prefix_match() -> None:
    sink = FakeSink()
    manager = LogManager(
        level=LOG_DEBUG,
        color_enabled=False,
        filter_mode="blacklist",
        filter_modules=("vision",),
        sinks=[sink],
    )

    manager.get_logger("vision.state").debug("drop")
    manager.get_logger("control.yaw").debug("keep")

    assert sink.lines == ["D [control.yaw   ] keep\r\n"]


def test_logger_matches_prefix_only_on_dot_boundary() -> None:
    sink = FakeSink()
    manager = LogManager(
        level=LOG_DEBUG,
        color_enabled=False,
        filter_mode="whitelist",
        filter_modules=("vision",),
        sinks=[sink],
    )

    manager.get_logger("vision").debug("keep-root")
    manager.get_logger("vision.state").debug("keep-child")
    manager.get_logger("visionary.state").debug("drop")

    assert sink.lines == [
        "D [vision        ] keep-root\r\n",
        "D [vision.state  ] keep-child\r\n",
    ]


def test_logger_off_mode_allows_any_module_above_level() -> None:
    sink = FakeSink()
    manager = LogManager(
        level=LOG_INFO,
        color_enabled=False,
        filter_mode="off",
        filter_modules=("vision",),
        sinks=[sink],
    )

    manager.get_logger("control.yaw").debug("hidden")
    manager.get_logger("control.yaw").info("shown")

    assert sink.lines == ["I [control.yaw   ] shown\r\n"]


def test_plain_formatter_keeps_logs_readable_without_color() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_DEBUG, color_enabled=False, sinks=[sink])

    manager.get_logger("control.yaw").debug("err=12.5")

    assert sink.lines == ["D [control.yaw   ] err=12.5\r\n"]


def test_legacy_sink_with_only_write_still_receives_formatted_output() -> None:
    sink = LegacySink()
    manager = LogManager(level=LOG_INFO, color_enabled=False, sinks=[sink])

    manager.get_logger("system.boot").info("legacy ok")

    assert sink.lines == ["I [system.boot   ] legacy ok\r\n"]


def test_color_formatter_can_be_enabled_for_output() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=True, sinks=[sink])

    manager.get_logger("system.boot").info("init ok")

    assert sink.lines == ["\x1b[32mI [system.boot   ] init ok\x1b[0m\r\n"]


def test_formatter_sanitizes_message_to_single_line_ascii() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_DEBUG, color_enabled=False, sinks=[sink])

    manager.get_logger("control.yaw").debug("err\r\n\t=\x01\u4f60")

    assert sink.lines == ["D [control.yaw   ] err   =??\r\n"]


def test_formatter_sanitizes_module_name_before_formatting() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=False, sinks=[sink])

    manager.get_logger("imu\n\t\u03c9").info("ready")

    assert sink.lines == ["I [imu  ?        ] ready\r\n"]


def test_formatter_truncates_overlong_module_column() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=False, sinks=[sink])

    manager.get_logger("vision.module.extra.long.name").info("ready")

    assert sink.lines == ["I [vision.module+] ready\r\n"]


def test_low_priority_log_drops_only_current_entry_on_format_memory_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=False, sinks=[sink])
    logger = manager.get_logger("vision.state")
    calls: list[tuple[int, str, str, bool]] = []

    original = manager_module.format_log_record

    def raise_once(
        level: int, module_name: str, message: str, color_enabled: bool = False
    ) -> str:
        calls.append((level, module_name, message, color_enabled))
        if len(calls) == 1:
            raise MemoryError("format oom")
        return original(level, module_name, message, color_enabled)

    monkeypatch.setattr(manager_module, "format_log_record", raise_once)

    logger.info("POLL")
    logger.info("POLL")

    assert calls == [
        (LOG_INFO, "vision.state", "POLL", False),
        (LOG_INFO, "vision.state", "POLL", False),
    ]
    assert sink.lines == ["I [vision.state  ] POLL\r\n"]


def test_important_log_falls_back_when_formatter_runs_out_of_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=False, sinks=[sink])

    def raise_memory_error(*_args, **_kwargs):
        raise MemoryError("format oom")

    monkeypatch.setattr(manager_module, "format_log_record", raise_memory_error)

    manager.get_logger("vision.state").error("shown")

    assert sink.lines == ["E [log.oom       ] format oom\r\n"]


def test_log_manager_reports_format_and_sink_oom_via_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    manager = LogManager(
        level=LOG_INFO,
        color_enabled=False,
        sinks=[MemoryErrorSink()],
        oom_callback=events.append,
    )

    def raise_memory_error(*_args, **_kwargs):
        raise MemoryError("format oom")

    monkeypatch.setattr(manager_module, "format_log_record", raise_memory_error)

    manager.get_logger("vision.state").error("shown")

    assert events == ["format", "sink"]


def test_busy_sink_drops_debug_before_error() -> None:
    sink = RingBufferSink(max_lines=1)
    manager = LogManager(level=LOG_DEBUG, color_enabled=False, sinks=[sink])
    logger = manager.get_logger("vision.state")

    logger.debug("drop-me")
    logger.error("keep-me")

    assert sink.snapshot() == ["E [vision.state  ] keep-me\r\n"]


def test_ring_buffer_keeps_existing_error_over_later_debug() -> None:
    sink = RingBufferSink(max_lines=1)
    manager = LogManager(level=LOG_DEBUG, color_enabled=False, sinks=[sink])
    logger = manager.get_logger("vision.state")

    logger.log(LOG_ERROR, "keep-me")
    logger.debug("drop-me")

    assert sink.snapshot() == ["E [vision.state  ] keep-me\r\n"]


def test_ring_buffer_rotates_among_equal_severity_entries_when_full() -> None:
    sink = RingBufferSink(max_lines=2)
    manager = LogManager(level=LOG_DEBUG, color_enabled=False, sinks=[sink])

    manager.get_logger("vision.a").debug("first")
    manager.get_logger("vision.b").debug("second")
    manager.get_logger("vision.c").debug("third")

    assert sink.snapshot() == [
        "D [vision.b      ] second\r\n",
        "D [vision.c      ] third\r\n",
    ]


def test_ring_buffer_replaces_oldest_lowest_severity_when_full() -> None:
    sink = RingBufferSink(max_lines=3)
    manager = LogManager(level=LOG_DEBUG, color_enabled=False, sinks=[sink])

    manager.get_logger("vision.a").debug("old-debug")
    manager.get_logger("vision.b").error("keep-error")
    manager.get_logger("vision.c").debug("newer-debug")
    manager.get_logger("vision.d").debug("latest-debug")

    assert sink.snapshot() == [
        "E [vision.b      ] keep-error\r\n",
        "D [vision.c      ] newer-debug\r\n",
        "D [vision.d      ] latest-debug\r\n",
    ]


def test_ring_buffer_rejects_non_positive_capacity() -> None:
    with pytest.raises(ValueError, match="max_lines must be > 0"):
        RingBufferSink(max_lines=0)


def test_log_manager_has_no_profile_field() -> None:
    manager = LogManager()

    assert not hasattr(manager, "profile")


def test_log_manager_rejects_invalid_filter_mode() -> None:
    with pytest.raises(ValueError, match="invalid filter_mode"):
        LogManager(filter_mode="bad")
