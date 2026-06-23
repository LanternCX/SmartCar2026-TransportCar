"""日志工具测试.

@file tests/unit/entry/test_startup_log.py
"""

import sys

from utils import startup_log


def test_log_prints_consistent_text(capsys, monkeypatch) -> None:
    """日志工具必须直接打印到标准输出."""

    startup_log.cnt = 0
    monkeypatch.setattr(startup_log, "_now_ms", lambda: 1234)

    message = startup_log.log("remote_control", "ticker started")
    output = capsys.readouterr().out

    assert message == "0 1234ms remote_control: ticker started"
    assert output.endswith("\n")
    assert message in output
    assert startup_log.cnt == 1


def test_log_exception_prints_summary_and_full_trace(capsys, monkeypatch) -> None:
    """异常日志入口必须同时输出摘要和完整调用链."""

    startup_log.cnt = 0
    monkeypatch.setattr(startup_log, "_now_ms", lambda: 1234)
    trace_calls = []

    monkeypatch.setattr(
        sys,
        "print_exception",
        lambda exc, file=None: (
            trace_calls.append(type(exc).__name__),
            print("Traceback (most recent call last):", file=file),
            print("RuntimeError: %s" % exc, file=file),
        )[-1],
        raising=False,
    )

    startup_log.log_exception("master_error", "role cycle failed: boom", RuntimeError("boom"))
    output = capsys.readouterr().out

    assert "0 1234ms master_error: role cycle failed: boom" in output
    assert "master_error: traceback start" in output
    assert "Traceback (most recent call last):" in output
    assert "RuntimeError: boom" in output
    assert "master_error: traceback end" in output
    assert trace_calls == ["RuntimeError"]


def test_write_exception_trace_uses_single_argument_when_stdout_stream_is_required(
    monkeypatch,
) -> None:
    """板端直接打印调用链时必须使用单参数 print_exception."""

    calls = []

    def _fake_print_exception(*args):
        calls.append(args)

    monkeypatch.setattr(
        sys,
        "print_exception",
        _fake_print_exception,
        raising=False,
    )

    startup_log.write_exception_trace(None, RuntimeError("boom"))

    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert str(calls[0][0]) == "boom"
