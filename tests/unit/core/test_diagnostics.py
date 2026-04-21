"""`core.diagnostics` 测试."""

from core.diagnostics import format_observe_line, format_query_response, format_snapshot_value


def test_format_snapshot_value_formats_none_as_none_text() -> None:
    """空值继续统一编码为 `none`."""

    assert format_snapshot_value(None) == "none"


def test_format_snapshot_value_sanitizes_regular_value() -> None:
    """普通值继续走单行清理逻辑."""

    assert format_snapshot_value("x\n1,2") == "x 1;2"


def test_format_query_response_formats_snapshot_as_query_line() -> None:
    """查询回包继续使用 `?token=` 口径."""

    line = format_query_response("health", {"alive": 1, "last_err": "ok"})

    assert line == "?health=alive:1,last_err:ok\r\n"


def test_format_observe_line_formats_snapshot_as_observe_line() -> None:
    """观测行继续使用 `OBSERVE` 口径."""

    line = format_observe_line("tick", {"count": 3, "overrun": 0})

    assert line == "OBSERVE tick count=3 overrun=0"
