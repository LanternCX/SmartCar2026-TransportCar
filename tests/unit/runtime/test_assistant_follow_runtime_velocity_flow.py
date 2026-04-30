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


def test_assistant_follow_runtime_fuses_feedforward_and_vision_velocity(monkeypatch) -> None:
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
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": 1.25,
        "vy": 1.5,
        "omega": 0.5,
        "has_omega": True,
    }
    assert runtime._transport_car.control_state == {"vx": 1.25, "vy": 1.5, "omega": 0.5}


def test_assistant_follow_runtime_records_uart8_v_packet_as_feedforward_source(
    monkeypatch,
) -> None:
    """UART8 的 v 短包进入前馈来源."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,2.0,0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime._inputs["uart8"]["velocity"] == {
        "vx": 1.0,
        "vy": 2.0,
        "omega": 0.5,
        "has_omega": True,
    }
    assert runtime._inputs["uart6"]["velocity"] is None
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": 1.0,
        "vy": 2.0,
        "omega": 0.5,
        "has_omega": True,
    }


def test_assistant_follow_runtime_records_uart6_v_packet_as_vision_source(
    monkeypatch,
) -> None:
    """UART6 的 v 短包进入视觉来源."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart(["v,0.25,-0.5,9.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime._inputs["uart6"]["velocity"] == {
        "vx": 0.25,
        "vy": -0.5,
        "omega": 0.0,
        "has_omega": False,
    }
    assert runtime._inputs["uart8"]["velocity"] is None
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": 0.25,
        "vy": -0.5,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_follow_runtime_requires_structured_velocity_entry(monkeypatch) -> None:
    """辅车融合速度只调用共享底盘结构化速度入口."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,2.0,0.5\n"
    uart6 = _FakeUart(["v,0.25,-0.5,9.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)
    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    delattr(type(runtime._transport_car), "handle_velocity_packet")

    runtime.step()

    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert not any(event[0] == "finalize_route" for event in events)
    assert runtime._last_error_text.startswith("role_cycle failed:")


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
    assert runtime._transport_car.control_state == {"vx": -0.5, "vy": 0.25, "omega": 0.0}


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

    assert runtime._transport_car.control_state == {"vx": 2.5, "vy": 0.75, "omega": 0.5}


def test_assistant_follow_runtime_zero_vision_packet_only_clears_uart6_contribution(monkeypatch) -> None:
    """UART6 显式零包只清视觉侧自己的平移贡献."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,2.0,1.0,0.5\n"
    uart6 = _FakeUart(["v,0.5,-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    after_both_active = dict(runtime._transport_car.control_state)
    uart6._buffer = b"v,0,0\n"
    runtime.step()

    assert after_both_active == {"vx": 2.5, "vy": 0.75, "omega": 0.5}
    assert runtime._transport_car.control_state == {"vx": 2.0, "vy": 1.0, "omega": 0.5}


def test_assistant_follow_runtime_zero_feedforward_packet_only_clears_uart8_contribution(monkeypatch) -> None:
    """UART8 显式零包只清前馈侧自己的贡献."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,2.0,1.0,0.5\n"
    uart6 = _FakeUart(["v,0.5,-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    after_both_active = dict(runtime._transport_car.control_state)
    uart8._buffer = b"v,0,0,0\n"
    runtime.step()

    assert after_both_active == {"vx": 2.5, "vy": 0.75, "omega": 0.5}
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": 0.5,
        "vy": -0.25,
        "omega": 0.0,
        "has_omega": True,
    }
    assert runtime._transport_car.control_state == {"vx": 0.5, "vy": -0.25, "omega": 0.0}


def test_assistant_follow_runtime_rejects_non_short_packet_velocity_input(monkeypatch) -> None:
    """非短包速度文本不能更新辅车速度输入."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,vy=2.0,omega=0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert not any(event[0] == "handle_velocity" for event in events)
    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_consumes_short_packet_directly(
    monkeypatch,
) -> None:
    """辅车运行时直接消费速度短包."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,2.0,0.5\nx=9,y=8\n"
    uart6 = _FakeUart(["v,0.25,-0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    routed_lines = [event for event in events if event[0] == "handle_uart_line"]
    assert routed_lines == []
    assert runtime._transport_car.control_state == {"vx": 1.25, "vy": 1.5, "omega": 0.5}


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


def test_assistant_follow_runtime_ignores_earlier_sync_without_context_rollback(monkeypatch) -> None:
    """序号较早的同步包不会回退本地同步上下文."""

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
