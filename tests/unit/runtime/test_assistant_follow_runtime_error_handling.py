"""辅车角色运行时异常与错误测试.

@file tests/unit/runtime/test_assistant_follow_runtime_error_handling.py
"""

from .assistant_follow_runtime_support import (
    _FakeUart,
    import_assistant_module,
    install_fake_transport_car,
    install_fake_uart6_factory,
)
import builtins


def test_assistant_follow_runtime_keeps_running_and_records_uart_errors(
    monkeypatch,
) -> None:
    """串口读取异常不能把角色层 step 炸掉，并且要留下最小错误信息。"""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"broken"
    uart8.read_error = ValueError("uart8 boom")
    uart6 = _FakeUart()
    uart6._buffer = b"\xff\n"
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    initial_cmd = dict(runtime._transport_car.control_state)

    keep_running = runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert keep_running is False
    assert runtime._transport_car.control_state == initial_cmd
    assert snapshot["state"] == "idle"
    assert snapshot["uart6_input_status"] == "error"
    assert snapshot["uart8_input_status"] == "error"
    assert snapshot["last_error_text"] == "uart8 read failed: uart8 boom"


def test_assistant_follow_runtime_catches_uart_any_errors(
    monkeypatch,
) -> None:
    """串口 any 异常要被按来源捕获并记录。"""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    def _raise_any():
        raise RuntimeError("uart8 any boom")

    uart8.any = _raise_any
    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert snapshot["uart8_input_status"] == "error"
    assert snapshot["last_error_text"] == "uart8 any failed: uart8 any boom"


def test_assistant_follow_runtime_keeps_uart8_effective_velocity_when_uart6_packet_is_invalid(
    monkeypatch,
) -> None:
    """UART6 当前包非法时, UART8 的有效速度仍要继续走完整角色链路."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.5,0.0,0.25\n"
    uart6 = _FakeUart(["v,0.5,bad"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    keep_running = runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert keep_running is False
    assert runtime._transport_car.control_state == {"vx": 1.5, "vy": 0.0, "omega": 0.25}
    assert ("handle_velocity", "assistant", 1.5, 0.0, 0.25) in events
    assert snapshot["uart6_input_status"] == "invalid"
    assert snapshot["uart8_input_status"] == "active"


def test_assistant_follow_runtime_records_uart8_decode_errors_symmetrically(
    monkeypatch,
) -> None:
    """UART8 解码错误也要像 UART6 一样按来源单独记录。"""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"\xff\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    keep_running = runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert keep_running is False
    assert snapshot["uart8_input_status"] == "error"
    assert snapshot["last_error_text"] == (
        "uart8 decode failed: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"
    )


def test_assistant_follow_runtime_decode_error_does_not_depend_on_builtin_exception_name(
    monkeypatch,
) -> None:
    """板端缺少 UnicodeDecodeError 名称时, 解码异常仍要被记录."""

    monkeypatch.delattr(builtins, "UnicodeDecodeError")
    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"\xff\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert snapshot["uart8_input_status"] == "error"
    assert snapshot["last_error_text"].startswith("uart8 decode failed:")
    assert "UnicodeDecodeError" not in snapshot["last_error_text"]


def test_assistant_follow_runtime_rejects_unknown_sync_state_without_ack(
    monkeypatch,
) -> None:
    """未知辅车子状态不能被当成已处理同步。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,99,0,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert runtime.sync_context is None
    assert runtime._sync_apply_count == 0
    assert uart8.messages == []
    assert snapshot["last_error_text"] == "unknown assistant sync state: 99"


def test_assistant_follow_runtime_catches_uart8_reliable_ack_write_error(
    monkeypatch,
) -> None:
    """UART8 可靠 ACK 写失败要被捕获并记录。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,1,1,0\n"
    uart8.write_error = RuntimeError("uart8 boom")
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert runtime._sync_apply_count == 1
    assert uart8.messages == []
    assert snapshot["last_error_text"] == "uart8 write failed: uart8 boom"


def test_assistant_follow_runtime_bounds_oversized_uart8_input(
    monkeypatch,
) -> None:
    """UART8 超长输入不能无限积压缓冲。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"x" * 300
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert runtime._inputs["uart8"]["buffer"] == ""
    assert uart8._buffer == b""
    assert snapshot["uart8_input_status"] == "invalid"
    assert snapshot["last_error_text"] == "none"
    assert _uart3.messages == []


def test_assistant_follow_runtime_bounds_oversized_uart6_input(
    monkeypatch,
) -> None:
    """UART6 超长输入不能无限积压缓冲。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart()
    uart6._buffer = b"x" * 300
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert runtime._inputs["uart6"]["buffer"] == ""
    assert uart6._buffer == b""
    assert snapshot["uart6_input_status"] == "invalid"
    assert snapshot["last_error_text"] == "none"
    assert _uart3.messages == []


def test_assistant_follow_runtime_parses_reliable_packet_before_uart8_overflow_tail(
    monkeypatch,
) -> None:
    """UART8 超长积压时, 限制窗口内的可靠包仍要先被处理。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"x\ns,12,1,1,0\n" + b"z" * 300
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert runtime._sync_apply_count == 1
    assert uart8.messages == ["a,12\r\n"]
    assert uart8._buffer == b""
    assert snapshot["assistant_state"] == follow_runtime_module.ASSISTANT_STATE_FOLLOW
    assert snapshot["uart8_input_status"] == "idle"
    assert _uart3.messages == []


def test_assistant_follow_runtime_limits_single_uart_read_size(
    monkeypatch,
) -> None:
    """辅车单次串口读取长度不能随硬件缓存无限放大。"""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    oversized_input = b"x" * (follow_runtime_module._INPUT_LIMIT + 200)
    uart6._buffer = oversized_input
    uart8._buffer = oversized_input

    runtime.step()

    assert uart6.read_sizes
    assert uart8.read_sizes
    assert max(uart6.read_sizes) <= follow_runtime_module._INPUT_LIMIT
    assert max(uart8.read_sizes) <= follow_runtime_module._INPUT_LIMIT
    assert uart3.messages == []
