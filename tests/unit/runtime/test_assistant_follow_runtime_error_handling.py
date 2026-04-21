"""辅车角色运行时异常与错误测试.

@file tests/unit/runtime/test_assistant_follow_runtime_error_handling.py
"""

from .assistant_follow_runtime_support import (
    _FakeUart,
    import_assistant_module,
    install_fake_transport_car,
    install_fake_uart6_factory,
)


def test_assistant_follow_runtime_keeps_running_and_records_uart_errors(
    monkeypatch,
) -> None:
    """串口读取异常不能把角色层 step 炸掉，并且要留下最小错误信息。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"broken"
    uart8.read_error = ValueError("uart8 boom")
    uart6 = _FakeUart()
    uart6._buffer = b"\xff\n"
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    initial_cmd = dict(runtime._transport_car.last_cmd)

    keep_running = runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert keep_running is False
    assert runtime._transport_car.last_cmd == initial_cmd
    assert snapshot["state"] == "idle"
    assert snapshot["uart6_input_status"] == "error"
    assert snapshot["uart8_input_status"] == "error"
    assert snapshot["last_error_text"] == "uart8 read failed: uart8 boom"


def test_assistant_follow_runtime_keeps_uart8_effective_velocity_when_uart6_packet_is_invalid(
    monkeypatch,
) -> None:
    """UART6 当前包非法时, UART8 的有效速度仍要继续走完整角色链路."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.5,omega=0.25\n"
    uart6 = _FakeUart(["vx=0.5,vx=1.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    keep_running = runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert keep_running is False
    assert runtime._transport_car.last_cmd == {"vx": 1.5, "vy": 0.0, "omega": 0.25}
    assert ("handle_uart_line", "assistant", "vx=1.5,vy=0.0,omega=0.25") in events
    assert snapshot["uart6_input_status"] == "invalid"
    assert snapshot["uart8_input_status"] == "active"


def test_assistant_follow_runtime_records_uart8_decode_errors_symmetrically(
    monkeypatch,
) -> None:
    """UART8 解码错误也要像 UART6 一样按来源单独记录。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
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
