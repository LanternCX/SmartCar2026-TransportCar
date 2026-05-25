"""! @file tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py
@brief 辅车角色运行时短包速度与同步测试
"""

from .assistant_follow_runtime_support import (
    _FakeUart,
    FakeClock,
    import_assistant_module,
    install_fake_transport_car,
    install_fake_uart6_factory,
)


def _set_filtered_speeds(car, *speeds):
    for state, speed in zip(car.wheel_states, speeds):
        state["filtered_speed"] = float(speed)


def test_assistant_follow_runtime_fuses_feedforward_and_vision_velocity(monkeypatch) -> None:
    """! @brief 辅车融合速度短包后, 以结构化速度写入共享底盘"""

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
    """! @brief UART8 的 v 短包进入前馈来源"""

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
    """! @brief UART6 的 v 短包进入视觉来源"""

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
    """! @brief 辅车融合速度只调用共享底盘结构化速度入口"""

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
    """! @brief UART6 速度短包只贡献平移速度"""

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
    """! @brief 两路速度短包保持最新值并按既有融合规则相加"""

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
    """! @brief UART6 显式零包只清视觉侧自己的平移贡献"""

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
    """! @brief UART8 显式零包只清前馈侧自己的贡献"""

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
    """! @brief 非短包速度文本不能更新辅车速度输入"""

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
    """! @brief 辅车运行时直接消费速度短包"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,2.0,0.5\nx=9,y=8\n"
    uart6 = _FakeUart(["v,0.25,-0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    routed_lines = [event for event in events if event[0] == "handle_uart_line"]
    assert routed_lines == []
    assert uart3.messages == []
    assert runtime._transport_car.control_state == {"vx": 1.25, "vy": 1.5, "omega": 0.5}


def test_assistant_follow_runtime_records_sync_context_and_replies_ack(monkeypatch) -> None:
    """! @brief 辅车收到 UART8 状态同步短包后记录上下文并回复 ACK"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,1,1,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context == {"seq": 12, "state": 1, "target": 1, "arg": 0}
    assert uart8.messages == ["a,12\r\n"]
    assert runtime._sync_apply_count == 1


def test_assistant_state_machine_accepts_orbit_command(monkeypatch) -> None:
    """! @brief 辅车子状态机接受 orbit 子状态并记录固定上下文"""

    module = import_assistant_module("vision.assistant.state_machine", monkeypatch)
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(3, 1, 0)

    assert applied is True
    assert machine.state == 3
    assert machine.target == 1
    assert machine.arg == 0


def test_assistant_follow_runtime_orbit_sync_acks_and_uses_shared_orbit_entry(
    monkeypatch,
) -> None:
    """! @brief 辅车收到 orbit 同步后只走统一绕行入口并清空本地残留"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,3,1,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)
    follow_runtime_module._ASSISTANT_ORBIT_TARGET_DEG = -90.0
    follow_runtime_module._ASSISTANT_ORBIT_RADIUS_SCALE = 1.5

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime._inputs["uart6"]["velocity"] = {
        "vx": 0.25,
        "vy": -0.5,
        "omega": 0.0,
        "has_omega": False,
    }
    runtime._inputs["uart8"]["velocity"] = {
        "vx": 1.0,
        "vy": 2.0,
        "omega": 0.5,
        "has_omega": True,
    }
    runtime._pending_local_vision_sync = {"seq": 3}
    runtime._pending_target_found_report = {"seq": 7}
    runtime._approach_target_found_done = True

    runtime.step()

    assert runtime.sync_context == {"seq": 12, "state": 3, "target": 1, "arg": 0}
    assert uart8.messages == ["a,12\r\n"]
    assert runtime._inputs["uart6"]["velocity"] is None
    assert runtime._inputs["uart8"]["velocity"] is None
    assert runtime._pending_local_vision_sync is None
    assert runtime._pending_target_found_report is None
    assert runtime._approach_target_found_done is False
    assert ("set_orbit_target", -90.0, 1.5) in events
    assert not any(event[0] == "handle_velocity" for event in events)
    assert runtime._transport_car.control_state == {
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "angle": -90.0,
    }
    assert runtime._transport_car.command_lock is True
    assert runtime._transport_car.orbit_mode is True


def test_assistant_follow_runtime_realigns_after_orbit_without_completion_report(
    monkeypatch,
) -> None:
    """! @brief 辅车绕行期间屏蔽速度输入, 到位后重新对正且不回报完成"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,10,2,1,1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nv,0.5,-0.25\nr,7,6,300\n" % local_sync_seq).encode()
    runtime.step()
    uart8._buffer = b"s,12,3,1,0\n"

    runtime.step()

    event_count = len(events)
    uart8._buffer = b"v,1.0,2.0,0.5\n"
    uart6._buffer = b"v,-0.25,0.5\n"
    runtime.step()

    assert not any(event[0] == "handle_velocity" for event in events[event_count:])
    assert runtime._inputs["uart6"]["velocity"] is None
    assert runtime._inputs["uart8"]["velocity"] is None
    assert runtime._pending_local_vision_sync is None
    assert runtime._pending_target_found_report is None
    assert runtime._transport_car.command_lock is True
    assert runtime._transport_car.orbit_mode is True
    assert uart8.messages == ["a,10\r\n", "r,7,6,300\r\n", "a,12\r\n"]

    runtime._transport_car.complete_orbit_on_next_step = True
    runtime.step()

    assert runtime._state_machine.state == 2
    assert runtime._pending_local_vision_sync is not None
    rearm_sync_seq = runtime._pending_local_vision_sync["seq"]
    assert uart6.messages[-1] == "s,%d,2,1,2\r\n" % rearm_sync_seq
    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}

    uart6._buffer = ("a,%d\nv,-0.5,0.25\nr,9,6,300\n" % rearm_sync_seq).encode()
    runtime.step()

    assert ("handle_velocity", "assistant", -0.5, 0.25, 0.0) in events
    assert runtime._transport_car.control_state == {
        "vx": -0.5,
        "vy": 0.25,
        "omega": 0.0,
        "angle": float(follow_runtime_module._ASSISTANT_ORBIT_TARGET_DEG),
    }
    assert runtime._transport_car.command_lock is True
    assert runtime._transport_car.orbit_mode is False
    assert runtime._state_machine.state == 2
    assert runtime._pending_target_found_report is None
    assert uart6.messages[-1] == "a,9\r\n"
    assert uart8.messages == ["a,10\r\n", "r,7,6,300\r\n", "a,12\r\n"]


def test_assistant_follow_runtime_enters_idle_and_clears_velocity_inputs(monkeypatch) -> None:
    """! @brief 辅车收到 idle 同步后清空两路速度并停止线速度"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,2.0,0.5\ns,12,0,0,0\n"
    uart6 = _FakeUart(["v,0.25,-0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context == {"seq": 12, "state": 0, "target": 0, "arg": 0}
    assert runtime._inputs["uart6"]["velocity"] is None
    assert runtime._inputs["uart8"]["velocity"] is None
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant_idle",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }
    assert ("handle_velocity", "assistant_idle", 0.0, 0.0, 0.0) in events
    assert uart8.messages == ["a,12\r\n"]


def test_assistant_follow_runtime_ignores_velocity_packets_while_idle(monkeypatch) -> None:
    """! @brief idle 后继续收到速度包不会恢复运动"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,0,0,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()

    event_count = len(events)
    uart8._buffer = b"v,1.0,2.0,0.5\n"
    uart6._buffer = b"v,0.25,-0.5\n"
    runtime.step()

    assert not any(event[0] == "handle_velocity" and event[1] == "assistant" for event in events[event_count:])
    assert runtime._inputs["uart6"]["velocity"] is None
    assert runtime._inputs["uart8"]["velocity"] is None
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant_idle",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_follow_runtime_follow_sync_rearms_local_vision_and_clears_motion(
    monkeypatch,
) -> None:
    """! @brief follow 同步同时切回本地色标跟随视觉任务并清空上一段运动"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,1,0,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime._transport_car.control_state = {
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "x": -0.12,
        "y": 0.0,
    }

    runtime.step()

    assert runtime._state_machine.state == follow_runtime_module.ASSISTANT_STATE_FOLLOW
    assert uart8.messages == ["a,12\r\n"]
    assert uart6.messages == ["s,100,1,0,0\r\n"]
    assert runtime._pending_local_vision_sync == {
        "seq": 100,
        "state": follow_runtime_module.ASSISTANT_STATE_FOLLOW,
        "target": 0,
        "arg": 0,
        "last_sent_ms": 100,
        "sent_once": True,
    }
    assert ("handle_velocity", "assistant_follow", 0.0, 0.0, 0.0) in events
    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_ignores_uart6_until_follow_vision_ack(
    monkeypatch,
) -> None:
    """! @brief follow 本地视觉未确认前不使用 UART6 色标速度"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,1,0,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    event_count = len(events)

    uart6._buffer = b"v,0.25,-0.5\n"
    runtime.step()

    assert ("handle_velocity", "assistant", 0.25, -0.5, 0.0) not in events[event_count:]

    uart6._buffer = b"a,100\nv,0.25,-0.5\n"
    runtime.step()

    assert ("handle_velocity", "assistant", 0.25, -0.5, 0.0) in events


def test_assistant_follow_runtime_ignores_master_vision_hook_sync(monkeypatch) -> None:
    """! @brief 辅车 UART8 不消费主车本地视觉 hook 同步包"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,7,3,1,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context is None
    assert uart8.messages == []
    assert runtime._last_error_text == "none"
    assert runtime._sync_apply_count == 0


def test_assistant_follow_runtime_repeats_ack_without_reapplying_same_sync(monkeypatch) -> None:
    """! @brief 重复同步包只重复 ACK, 不重复应用"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,1,1,0\ns,12,1,1,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert uart8.messages == ["a,12\r\n", "a,12\r\n"]
    assert runtime._sync_apply_count == 1


def test_assistant_follow_runtime_ignores_earlier_sync_without_context_rollback(monkeypatch) -> None:
    """! @brief 序号较早的同步包不会回退本地同步上下文"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,1,1,0\ns,11,0,0,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context == {"seq": 12, "state": 1, "target": 1, "arg": 0}
    assert uart8.messages == ["a,12\r\n", "a,11\r\n"]
    assert runtime._sync_apply_count == 1


def test_assistant_follow_runtime_does_not_apply_earlier_idle_after_newer_follow(
    monkeypatch,
) -> None:
    """! @brief 较早 idle 同步不能回滚较新的 follow 状态"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,1,1,0\ns,11,0,0,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime._state_machine.state == 1
    assert runtime.sync_context == {"seq": 12, "state": 1, "target": 1, "arg": 0}
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant_follow",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_follow_runtime_uart6_does_not_handle_sync_packet(monkeypatch) -> None:
    """! @brief UART6 不承担状态同步职责"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart(["s,12,3,1,0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.sync_context is None
    assert uart8.messages == []


def test_assistant_follow_runtime_approach_sync_clears_stale_velocity_and_waits_local_ack(
    monkeypatch,
) -> None:
    """! @brief 进入找物体后先清空残留速度, 并在本地视觉确认前保持零速"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"v,1.0,2.0,0.5\n"
    uart6 = _FakeUart(["v,0.25,-0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()

    uart8._buffer = b"s,12,2,1,1\n"
    uart6._buffer = b"v,9.0,8.0\n"
    runtime.step()

    local_sync_seq = runtime._pending_local_vision_sync["seq"]

    assert runtime.sync_context == {"seq": 12, "state": 2, "target": 1, "arg": 1}
    assert runtime._inputs["uart6"]["velocity"] is None
    assert runtime._inputs["uart8"]["velocity"] is None
    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert uart8.messages == ["a,12\r\n"]
    assert uart6.messages == ["s,%d,2,1,1\r\n" % local_sync_seq]

    clock.advance(10)
    uart6._buffer = b"v,3.0,4.0\n"
    runtime.step()

    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert uart6.messages == ["s,%d,2,1,1\r\n" % local_sync_seq]

    clock.advance(20)
    runtime.step()

    assert uart6.messages == [
        "s,%d,2,1,1\r\n" % local_sync_seq,
        "s,%d,2,1,1\r\n" % local_sync_seq,
    ]


def test_assistant_follow_runtime_approach_object_uses_only_uart6_after_local_ack(
    monkeypatch,
) -> None:
    """! @brief 找物体阶段只用本地视觉平移速度, 不叠加 UART8 前馈"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,2,1,1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart8._buffer = b"v,5.0,6.0,0.5\n"
    uart6._buffer = ("a,%d\nv,-0.5,0.25,9.0\n" % local_sync_seq).encode()

    runtime.step()

    assert ("handle_velocity", "assistant", -0.5, 0.25, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": -0.5,
        "vy": 0.25,
        "omega": 0.0,
        "has_omega": False,
    }
    assert runtime._transport_car.control_state == {"vx": -0.5, "vy": 0.25, "omega": 0.0}


def test_assistant_follow_runtime_reports_local_target_found_until_master_ack(
    monkeypatch,
) -> None:
    """! @brief 本地视觉找到目标后停止并向主车可靠回报直到收到确认"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"s,12,2,1,1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nv,0.5,-0.25\n" % local_sync_seq).encode()
    runtime.step()

    uart6._buffer = b"r,7,6,300\n"
    runtime.step()

    assert uart6.messages[-1] == "a,7\r\n"
    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert runtime._approach_target_found_done is True
    assert runtime._pending_target_found_report is not None
    assert uart8.messages[-1] == "r,7,6,300\r\n"

    sent_count = len(uart8.messages)
    clock.advance(10)
    runtime.step()
    assert len(uart8.messages) == sent_count

    clock.advance(20)
    runtime.step()
    assert uart8.messages[-1] == "r,7,6,300\r\n"
    assert len(uart8.messages) == sent_count + 1

    uart8._buffer = b"a,7\n"
    runtime.step()
    sent_count = len(uart8.messages)
    clock.advance(20)
    runtime.step()

    assert runtime._pending_target_found_report is None
    assert len(uart8.messages) == sent_count


def test_assistant_follow_runtime_keeps_orbit_heading_during_post_orbit_realign(
    monkeypatch,
) -> None:
    """! @brief 辅车绕行结束后的二次对正继续维持绕行目标角度"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"s,10,2,1,1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nr,7,6,300\n" % local_sync_seq).encode()
    runtime.step()
    uart8._buffer = b"s,12,3,1,0\n"
    runtime.step()
    runtime._transport_car.complete_orbit_on_next_step = True
    runtime.step()

    rearm_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nv,-0.5,0.25\n" % rearm_sync_seq).encode()
    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": -0.5,
        "vy": 0.25,
        "omega": 0.0,
        "has_omega": False,
    }
    assert runtime._transport_car.control_state["angle"] == float(
        follow_runtime_module._ASSISTANT_ORBIT_TARGET_DEG
    )


def test_assistant_follow_runtime_realign_phase_reports_aligned_after_orbit(
    monkeypatch,
) -> None:
    """! @brief 辅车绕行后回到二次对正阶段时, 本地视觉 ALIGNED 向主车回报就位"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"s,10,2,1,1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nr,7,6,300\n" % local_sync_seq).encode()
    runtime.step()
    uart8._buffer = b"s,12,3,1,0\n"
    runtime.step()
    runtime._transport_car.complete_orbit_on_next_step = True
    runtime.step()

    rearm_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nr,9,7,0\n" % rearm_sync_seq).encode()
    runtime.step()

    assert uart6.messages[-1] == "a,9\r\n"
    assert uart8.messages[-1] == "r,9,7,0\r\n"


def test_assistant_follow_runtime_realign_phase_repeats_aligned_until_master_ack(
    monkeypatch,
) -> None:
    """! @brief 辅车就位回报在收到主车 ACK 前按可靠机制重发"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"s,10,2,1,1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nr,7,6,300\n" % local_sync_seq).encode()
    runtime.step()
    uart8._buffer = b"s,12,3,1,0\n"
    runtime.step()
    runtime._transport_car.complete_orbit_on_next_step = True
    runtime.step()
    rearm_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nr,9,7,0\n" % rearm_sync_seq).encode()
    runtime.step()

    sent_count = len(uart8.messages)
    clock.advance(10)
    runtime.step()
    assert len(uart8.messages) == sent_count

    clock.advance(20)
    runtime.step()
    assert uart8.messages[-1] == "r,9,7,0\r\n"

    uart8._buffer = b"a,9\n"
    runtime.step()
    sent_count = len(uart8.messages)
    clock.advance(20)
    runtime.step()

    assert runtime._pending_target_found_report is None
    assert len(uart8.messages) == sent_count


def test_assistant_follow_runtime_transport_sync_uses_mirrored_feedforward_with_vision(
    monkeypatch,
) -> None:
    """! @brief 搬运态对 UART8 前馈做头对头换算后再叠加本车视觉修正"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,4,1,2\n"
    uart6 = _FakeUart(["v,0.5,-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart8._buffer = b"v,2.0,3.0,0.7\n"
    uart6._buffer = ("a,%d\nv,0.5,-0.25\n" % local_sync_seq).encode()
    runtime.step()

    scale = float(follow_runtime_module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE)
    assert (
        "handle_velocity",
        "assistant",
        0.5 - 2.0 * scale,
        -0.25 - 3.0 * scale,
        0.0,
    ) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": 0.5 - 2.0 * scale,
        "vy": -0.25 - 3.0 * scale,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_follow_runtime_transport_sync_scales_uart8_feedforward(
    monkeypatch,
) -> None:
    """! @brief 搬运态可按参数缩放 UART8 前馈后再叠加本车视觉修正"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,4,1,2\n"
    uart6 = _FakeUart(["v,0.5,-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)
    follow_runtime_module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE = 0.5

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart8._buffer = b"v,2.0,3.0,0.7\n"
    uart6._buffer = ("a,%d\nv,0.5,-0.25\n" % local_sync_seq).encode()
    runtime.step()

    assert ("handle_velocity", "assistant", -0.5, -1.75, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": -0.5,
        "vy": -1.75,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_follow_runtime_transport_sync_responds_with_only_uart8_feedforward(
    monkeypatch,
) -> None:
    """! @brief 搬运态只有 UART8 前馈时仍响应"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,4,1,2\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    uart8._buffer = b"v,2.0,3.0,0.7\n"
    runtime.step()

    scale = float(follow_runtime_module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE)
    assert ("handle_velocity", "assistant", -2.0 * scale, -3.0 * scale, 0.0) in events
    assert runtime._transport_car.control_state == {
        "vx": -2.0 * scale,
        "vy": -3.0 * scale,
        "omega": 0.0,
    }


def test_assistant_follow_runtime_transport_sync_responds_with_only_uart6_vision(
    monkeypatch,
) -> None:
    """! @brief 搬运态只有 UART6 视觉修正时仍响应"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,4,1,2\n"
    uart6 = _FakeUart(["v,0.5,-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    local_sync_seq = None
    runtime.step()
    local_sync_seq = runtime._pending_local_vision_sync["seq"]
    uart6._buffer = ("a,%d\nv,0.5,-0.25\n" % local_sync_seq).encode()
    runtime.step()

    assert ("handle_velocity", "assistant", 0.5, -0.25, 0.0) in events
    assert runtime._transport_car.control_state == {"vx": 0.5, "vy": -0.25, "omega": 0.0}


def test_assistant_follow_runtime_transport_sync_with_no_inputs_keeps_idle_output(
    monkeypatch,
) -> None:
    """! @brief 搬运态两路都没有输入时不主动生成新搬运速度"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,4,1,2\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    event_count = len(events)
    runtime.step()

    assert not any(event[0] == "handle_velocity" for event in events[event_count:])
    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_transport_sync_clears_previous_motion_immediately(
    monkeypatch,
) -> None:
    """! @brief 从上一阶段切入搬运态时先明确停住, 不沿用旧目标"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,2.0,0.5\n"
    uart6 = _FakeUart(["v,0.25,-0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    assert runtime._transport_car.control_state == {"vx": 1.25, "vy": 1.5, "omega": 0.5}

    uart8._buffer = b"s,12,4,1,2\n"
    runtime.step()

    assert ("handle_velocity", "assistant_transport", 0.0, 0.0, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant_transport",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }
    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_clear_sync_starts_retreat_step(
    monkeypatch,
) -> None:
    """! @brief 辅车收到脱离同步后先沿自身 Y 负方向后退半步"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,5,1,1\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()

    assert runtime._state_machine.state == follow_runtime_module.ASSISTANT_STATE_CLEAR_OBJECT
    assert (
        "set_relative_translation_target",
        0.0,
        -float(follow_runtime_module._TRANSPORT_CLEAR_STEP_DISTANCE_M) * 0.5,
    ) in events
    assert "a,12\r\n" in uart8.messages


def test_assistant_follow_runtime_clear_sync_starts_forward_step_after_turn_back(
    monkeypatch,
) -> None:
    """! @brief 辅车收到第二段脱离同步后再按自身 Y 正方向前进"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,5,1,2\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()

    assert runtime._state_machine.state == follow_runtime_module.ASSISTANT_STATE_CLEAR_OBJECT
    assert (
        "set_relative_translation_target",
        0.0,
        float(follow_runtime_module._TRANSPORT_CLEAR_STEP_DISTANCE_M),
    ) in events
    assert "a,12\r\n" in uart8.messages


def test_assistant_follow_runtime_clear_completion_reports_phase_cleared(
    monkeypatch,
) -> None:
    """! @brief 辅车位置动作完成后按当前脱离阶段回报完成"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"s,12,5,1,2\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)
    follow_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)
    runtime.step()
    runtime._transport_car.command_lock = False
    _set_filtered_speeds(runtime._transport_car, 1.0, 1.0, 1.0)

    runtime.step()

    assert uart8.messages == ["a,12\r\n"]

    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.advance(20)
    runtime.step()

    assert uart8.messages == ["a,12\r\n"]

    clock.advance(20)
    runtime.step()

    assert uart8.messages[-1] == "r,140,9,2\r\n"


def test_assistant_follow_runtime_transport_sync_ignores_uart8_omega(
    monkeypatch,
) -> None:
    """! @brief 搬运态不使用 UART8 的 omega"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,4,1,2\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module("vision.assistant.follow_runtime", monkeypatch)

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    uart8._buffer = b"v,2.0,3.0,0.7\n"
    runtime.step()

    scale = float(follow_runtime_module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE)
    assert ("handle_velocity", "assistant", -2.0 * scale, -3.0 * scale, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": -2.0 * scale,
        "vy": -3.0 * scale,
        "omega": 0.0,
        "has_omega": False,
    }
