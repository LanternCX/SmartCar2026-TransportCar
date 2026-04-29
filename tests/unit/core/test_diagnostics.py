"""`core.diagnostics` 测试."""

import core.diagnostics as diagnostics
from core.diagnostics import format_observe_line, format_snapshot_value


def test_format_snapshot_value_formats_none_as_none_text() -> None:
    """空值继续统一编码为 `none`."""

    assert format_snapshot_value(None) == "none"


def test_format_snapshot_value_sanitizes_regular_value() -> None:
    """普通值继续走单行清理逻辑."""

    assert format_snapshot_value("x\n1,2") == "x 1;2"


def test_diagnostics_has_no_query_response_formatter() -> None:
    """诊断工具不暴露通用查询回包格式化入口."""

    assert not hasattr(diagnostics, "format_query_response")


def test_format_observe_line_formats_snapshot_as_observe_line() -> None:
    """观测行继续使用 `OBSERVE` 口径."""

    line = format_observe_line("tick", {"count": 3, "overrun": 0})

    assert line == "OBSERVE tick count=3 overrun=0"
