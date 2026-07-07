"""日志工具测试.

@file tests/unit/entry/test_startup_log.py
"""

import sys
from types import ModuleType

from utils import startup_log


def test_log_prints_consistent_text(capsys, monkeypatch) -> None:
    """日志工具必须直接打印到标准输出."""

    startup_log.cnt = 0
    monkeypatch.setattr(startup_log, "_now_ms", lambda: 1234)

    message = startup_log.log("run", "ticker started")
    output = capsys.readouterr().out

    assert message == "0 1234ms run: ticker started"
    assert output.endswith("\n")
    assert message in output
    assert startup_log.cnt == 1


def test_log_memory_prints_short_heap_snapshot(capsys, monkeypatch) -> None:
    """内存日志只输出短标签和堆读数."""

    startup_log.cnt = 0
    monkeypatch.setattr(startup_log, "_now_ms", lambda: 1234)
    gc_module = ModuleType("gc")
    calls = []
    setattr(gc_module, "collect", lambda: calls.append("collect"))
    setattr(gc_module, "mem_free", lambda: 100)
    setattr(gc_module, "mem_alloc", lambda: 28)
    monkeypatch.setitem(sys.modules, "gc", gc_module)

    message = startup_log.log_memory("r0")
    output = capsys.readouterr().out

    assert message == "0 1234ms mem: r0 f=100 a=28 t=128"
    assert message in output
    assert calls == ["collect"]


def test_log_exception_prints_summary_without_trace_by_default(capsys, monkeypatch) -> None:
    """异常日志默认只输出短摘要."""

    startup_log.TRACE_EXCEPTION = False

    startup_log.cnt = 0
    monkeypatch.setattr(startup_log, "_now_ms", lambda: 1234)

    startup_log.log_exception("master_error", "role cycle failed: boom", RuntimeError("boom"))
    output = capsys.readouterr().out

    assert "0 1234ms master_error: role cycle failed: boom" in output
    assert "master_error: traceback start" not in output
    assert "master_error: traceback end" not in output


def test_log_exception_prints_full_trace_when_enabled(capsys, monkeypatch) -> None:
    """诊断开关启用时输出完整调用链."""

    startup_log.cnt = 0
    startup_log.TRACE_EXCEPTION = True
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
    startup_log.TRACE_EXCEPTION = False


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
