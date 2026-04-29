"""辅车角色运行时短包速度与同步测试.

@file tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py
"""

from .assistant_follow_runtime_support import (
    _FakeUart,
    FakeClock,
    import_assistant_module,
    install_fake_transport_car,
    install_fake_uart6_factory,
)


def test_assistant_follow_runtime_accepts_v_packets_without_key_value_writeback(monkeypatch) -> None:
    """辅车融合速度短包后, 以结构化速度写入共享底盘."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,2.0,0.5\n"
    uart6 = _FakeUart(["v,0.25,-0.5,9.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_velocity", "assistant", 1.25, 1.5, 0.5) in events
    assert not any(event[:2] == ("handle_uart_line", "assistant") for event in events)
    assert runtime._transport_car.last_cmd == {"vx": 1.25, "vy": 1.5, "omega": 0.5}


def test_assistant_follow_runtime_uart6_packet_only_contributes_vx_vy(monkeypatch) -> None:
    """UART6 速度短包只贡献平移速度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart(["v,-0.5,0.25,-1.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_velocity", "assistant", -0.5, 0.25, 0.0) in events
    assert runtime._transport_car.last_cmd == {"vx": -0.5, "vy": 0.25, "omega": 0.0}


def test_assistant_follow_runtime_keeps_last_packets_without_timeout(monkeypatch) -> None:
    """两路速度短包保持最新值并按既有融合规则相加."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"v,2.0,1.0,0.5\n"
    uart6 = _FakeUart(["v,0.5,-0.25,9.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    clock.advance(200)
    runtime.step()

    assert runtime._transport_car.last_cmd == {"vx": 2.5, "vy": 0.75, "omega": 0.5}


def test_assistant_follow_runtime_zero_vision_packet_only_clears_uart6_contribution(monkeypatch) -> None:
    """UART6 显式零包只清视觉侧自己的平移贡献."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,2.0,1.0,0.5\n"
    uart6 = _FakeUart(["v,0.5,-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    after_both_active = dict(runtime._transport_car.last_cmd)
    uart6._buffer = b"v,0,0\n"
    runtime.step()

    assert after_both_active == {"vx": 2.5, "vy": 0.75, "omega": 0.5}
    assert runtime._transport_car.last_cmd == {"vx": 2.0, "vy": 1.0, "omega": 0.5}


def test_assistant_follow_runtime_rejects_key_value_velocity_input(monkeypatch) -> None:
    """键值速度字段不能更新辅车速度输入."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,vy=2.0,omega=0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert not any(event[0] == "handle_velocity" for event in events)
    assert runtime._transport_car.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_keeps_non_velocity_passthrough(monkeypatch) -> None:
    """非速度底盘命令仍可透传给共享底盘."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"rear=1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert runtime._transport_car.rear_only_mode is True


def test_assistant_follow_runtime_strips_key_value_velocity_from_mixed_passthrough(monkeypatch) -> None:
    """混合输入中的键值速度字段不会透传进共享底盘速度入口."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,rear=1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert ("handle_uart_line", "uart8", "vx=1.0,rear=1") not in events
    assert runtime._transport_car.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_records_sync_context_and_replies_ack(monkeypatch) -> None:
    """辅车收到 UART8 状态同步短包后记录上下文并回复 ACK."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,3,1,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context == {"seq": 12, "state": 3, "target": 1, "arg": 0}
    assert uart8.messages == ["a,12\r\n"]
    assert runtime._sync_apply_count == 1


def test_assistant_follow_runtime_repeats_ack_without_reapplying_same_sync(monkeypatch) -> None:
    """重复同步包只重复 ACK, 不重复应用."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,3,1,0\ns,12,3,1,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert uart8.messages == ["a,12\r\n", "a,12\r\n"]
    assert runtime._sync_apply_count == 1


def test_assistant_follow_runtime_ignores_old_sync_without_context_rollback(monkeypatch) -> None:
    """旧同步包不会回退本地同步上下文."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,3,1,0\ns,11,4,2,9\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context == {"seq": 12, "state": 3, "target": 1, "arg": 0}
    assert uart8.messages == ["a,12\r\n", "a,11\r\n"]
    assert runtime._sync_apply_count == 1


def test_assistant_follow_runtime_uart6_does_not_handle_sync_packet(monkeypatch) -> None:
    """UART6 不承担状态同步职责."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart(["s,12,3,1,0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context is None
    assert uart8.messages == []
