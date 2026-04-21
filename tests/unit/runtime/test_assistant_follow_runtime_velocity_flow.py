"""辅车角色运行时速度与输入流测试.

@file tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py
"""

from .assistant_follow_runtime_support import (
    _FakeUart,
    FakeClock,
    import_assistant_module,
    install_fake_transport_car,
    install_fake_uart6_factory,
)


def test_assistant_follow_runtime_prioritizes_role_inputs_and_routes_effective_speed_through_transport(
    monkeypatch,
) -> None:
    """辅车角色层要保留前馈和视觉修正，但最终速度仍走共享底盘入口。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0\n?health\nrear=1\n"
    uart6 = _FakeUart(["vx=0.5,vy=-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert ("handle_uart_line", "uart8", "vx=1.0") not in events
    assert ("handle_uart_line", "uart6", "vx=0.5,vy=-0.25") not in events
    assert ("handle_uart_line", "uart8", "?health") in events
    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.5, "vy": -0.25, "omega": 0.0}
    assert runtime._transport_car.rear_only_mode is True
    assert runtime._transport_car.command_lock is False
    assert runtime._transport_car.command_mode == "none"


def test_assistant_follow_runtime_routes_corrected_speed_through_transport_when_vision_is_present(
    monkeypatch,
) -> None:
    """视觉输入存在时，修正后的速度也必须通过共享底盘入口生效。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,vy=-2.0,omega=0.5\n"
    uart6 = _FakeUart(["vx=0.5,vy=-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_uart_line", "uart8", "vx=1.0,vy=-2.0,omega=0.5") not in events
    assert ("handle_uart_line", "assistant", "vx=1.5,vy=-2.25,omega=0.5") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.5, "vy": -2.25, "omega": 0.5}


def test_assistant_follow_runtime_keeps_last_uart8_velocity_without_old_timeout(
    monkeypatch,
) -> None:
    """UART8 速度命令应像 UART3 一样持续生效，不能沿用旧的超时清零语义。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b"vx=2.0,omega=0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    clock.advance(200)
    runtime.step()

    assert runtime._transport_car.last_cmd == {"vx": 2.0, "vy": 0.0, "omega": 0.5}


def test_assistant_follow_runtime_keeps_last_uart6_vx_vy_without_extra_timeout(
    monkeypatch,
) -> None:
    """UART6 视觉输入也应持续保持上一包，但只保留自己的 vx 和 vy 贡献。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = FakeClock(100)
    uart8._buffer = b""
    uart6 = _FakeUart(["vx=-4.6,vy=0.25,omega=1.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    clock.advance(200)
    uart8._buffer = b"vx=0,vy=0,omega=0\n"
    runtime.step()

    assert runtime._transport_car.last_cmd == {"vx": -4.6, "vy": 0.25, "omega": 0.0}


def test_assistant_follow_runtime_uart6_packet_only_contributes_vx_vy(
    monkeypatch,
) -> None:
    """UART6 视觉包只贡献 vx 和 vy，不能把自身 omega 带进最终输出。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart(["vy=0.25, omega=-1.5, vx=-0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime._transport_car.last_cmd == {"vx": -0.5, "vy": 0.25, "omega": 0.0}


def test_assistant_follow_runtime_matches_uart8_and_uart6_for_same_velocity_vector(
    monkeypatch,
) -> None:
    """同一速度向量分别从 UART8 和 UART6 进入时，应形成相同的底盘速度结果。"""

    _events_uart8, _uart3_a, uart8_a = install_fake_transport_car(monkeypatch)
    uart8_a._buffer = b"vx=-4.6,vy=0\n"
    uart6_a = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6_a)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )
    runtime_uart8 = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime_uart8.step()

    _events_uart6, _uart3_b, uart8_b = install_fake_transport_car(monkeypatch)
    uart8_b._buffer = b""
    uart6_b = _FakeUart(["vx=-4.6,vy=0"])
    install_fake_uart6_factory(monkeypatch, uart6_b)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )
    runtime_uart6 = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime_uart6.step()

    assert runtime_uart8._transport_car.last_cmd == {
        "vx": -4.6,
        "vy": 0.0,
        "omega": 0.0,
    }
    assert runtime_uart6._transport_car.last_cmd == {
        "vx": -4.6,
        "vy": 0.0,
        "omega": 0.0,
    }


def test_assistant_follow_runtime_uart6_velocity_reclaims_control_after_position_mode(
    monkeypatch,
) -> None:
    """UART6 新速度包到来后，也要像 UART8 一样从位置目标手里接回控制权。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"x=12.0,angle=45.0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    uart6._buffer = b"vx=-4.6,vy=0\n"
    runtime.step()

    assert runtime._transport_car.last_cmd == {"vx": -4.6, "vy": 0.0, "omega": 0.0}
    assert runtime._transport_car.command_lock is False
    assert runtime._transport_car.command_mode == "none"


def test_assistant_follow_runtime_zero_feedforward_packet_clears_old_omega_before_adding_vision(
    monkeypatch,
) -> None:
    """前馈显式零包后，视觉叠加结果不能继续带着旧的 omega 残留。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=0,vy=0,omega=3\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )
    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    uart8._buffer = b"vx=0,vy=0,omega=0\n"
    uart6._buffer = b"vx=-4.6,vy=0\n"

    runtime.step()

    assert runtime._transport_car.last_cmd == {"vx": -4.6, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_zero_vision_packet_only_clears_uart6_contribution(
    monkeypatch,
) -> None:
    """UART6 显式零包只清视觉侧自己的 vx 和 vy，不能把 UART8 前馈贡献一起清掉。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=2.0,vy=1.0,omega=0.5\n"
    uart6 = _FakeUart(["vx=0.5,vy=-0.25\n"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    after_both_active = dict(runtime._transport_car.last_cmd)
    uart6._buffer = b"vx=0,vy=0\n"
    runtime.step()
    after_uart6_zero = dict(runtime._transport_car.last_cmd)

    assert after_both_active == {"vx": 2.5, "vy": 0.75, "omega": 0.5}
    assert after_uart6_zero == {"vx": 2.0, "vy": 1.0, "omega": 0.5}


def test_assistant_follow_runtime_async_inputs_keep_last_packet_without_waiting(
    monkeypatch,
) -> None:
    """两路异步到包时不互相等待，UART6 保持上一包并与 UART8 新包直接裸相加。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart(["vx=0.5,vy=-0.25,omega=9.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    after_uart6_only = dict(runtime._transport_car.last_cmd)
    uart8._buffer = b"vx=2.0,vy=1.0,omega=0.5\n"
    runtime.step()
    after_uart8_updates = dict(runtime._transport_car.last_cmd)

    assert after_uart6_only == {"vx": 0.5, "vy": -0.25, "omega": 0.0}
    assert after_uart8_updates == {"vx": 2.5, "vy": 0.75, "omega": 0.5}


def test_assistant_follow_runtime_routes_velocity_back_through_transport_when_vision_is_missing(
    monkeypatch,
) -> None:
    """无视觉时的速度写回仍要走共享底盘入口，而不是角色层直写内部状态。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=2.0,vy=-1.0,omega=0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    routed = []

    def routed_handle(line: str, source: str) -> None:
        routed.append((source, line))
        dispatched = set()
        for fragment in line.split(","):
            item = fragment.strip()
            if not item or "=" not in item:
                continue
            key, value_text = item.split("=", 1)
            key = key.strip()
            if key not in ("vx", "vy", "omega"):
                continue
            runtime._transport_car.last_cmd[key] = float(value_text)
            dispatched.add(key)
        if dispatched:
            runtime._transport_car._finalize_route(dispatched)

    monkeypatch.setattr(runtime._transport_car, "_handle_uart_line", routed_handle)
    runtime._transport_car.command_lock = True
    runtime._transport_car.command_mode = "locked"

    runtime.step()

    assert routed == [("assistant", "vx=2.0,vy=-1.0,omega=0.5")]
    assert runtime._transport_car.last_cmd == {"vx": 2.0, "vy": -1.0, "omega": 0.5}
    assert runtime._transport_car.command_lock is False
    assert runtime._transport_car.command_mode == "none"


def test_assistant_follow_runtime_intercepts_velocity_fields_inside_mixed_uart8_packet(
    monkeypatch,
) -> None:
    """混合包里的速度字段要先被角色层接管，再把修正后的速度交回共享底盘。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,vy=2.0,rear=1\n"
    uart6 = _FakeUart(["vx=0.25,vy=0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_uart_line", "uart8", "vx=1.0") not in events
    assert ("handle_uart_line", "uart8", "vy=2.0") not in events
    assert ("handle_uart_line", "uart8", "vx=1.0,vy=2.0,rear=1") not in events
    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.25, "vy": 2.5, "omega": 0.0}
    assert runtime._transport_car.rear_only_mode is True


def test_assistant_follow_runtime_intercepts_velocity_fields_inside_mixed_uart6_packet(
    monkeypatch,
) -> None:
    """UART6 混合包也要先截取视觉速度字段，再把其余字段透传到底盘。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,vy=2.0\n"
    uart6 = _FakeUart(["vx=0.25,vy=0.5,omega=7.0,rear=1"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_uart_line", "uart6", "vx=0.25") not in events
    assert ("handle_uart_line", "uart6", "vy=0.5") not in events
    assert ("handle_uart_line", "uart6", "vx=0.25,vy=0.5,omega=7.0,rear=1") not in events
    assert ("handle_uart_line", "uart6", "rear=1") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.25, "vy": 2.5, "omega": 0.0}
    assert runtime._transport_car.rear_only_mode is True


def test_assistant_follow_runtime_preserves_position_and_angle_passthrough_commands(
    monkeypatch,
) -> None:
    """位置和角度透传命令生效后，角色层不能立刻再用速度写回把它们冲掉。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,x=12.0,angle=45.0\n"
    uart6 = _FakeUart(["vx=0.5,vy=0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    first_cmd = dict(runtime._transport_car.last_cmd)
    runtime.step()
    second_cmd = dict(runtime._transport_car.last_cmd)

    assert ("handle_uart_line", "uart8", "x=12.0,angle=45.0") in events
    assert first_cmd["x"] == 12.0
    assert first_cmd["angle"] == 45.0
    assert "vx" not in first_cmd
    assert second_cmd["x"] == 12.0
    assert second_cmd["angle"] == 45.0
    assert "vx" not in second_cmd


def test_assistant_follow_runtime_preserves_uart6_position_passthrough_commands(
    monkeypatch,
) -> None:
    """UART6 透传出位置目标后, 角色层也不能立刻再写回速度把它冲掉."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0\n"
    uart6 = _FakeUart(["vx=0.5,x=12.0,angle=45.0"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    first_cmd = dict(runtime._transport_car.last_cmd)
    runtime.step()
    second_cmd = dict(runtime._transport_car.last_cmd)

    assert ("handle_uart_line", "uart6", "x=12.0,angle=45.0") in events
    assert first_cmd["x"] == 12.0
    assert first_cmd["angle"] == 45.0
    assert "vx" not in first_cmd
    assert second_cmd["x"] == 12.0
    assert second_cmd["angle"] == 45.0
    assert "vx" not in second_cmd


def test_assistant_follow_runtime_new_velocity_packet_reclaims_control_after_position_mode(
    monkeypatch,
) -> None:
    """位置命令保住后，新的速度包仍要能让角色层重新接管。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"x=12.0,angle=45.0\n"
    uart6 = _FakeUart(["vx=0.5,vy=0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    after_position = dict(runtime._transport_car.last_cmd)
    uart8._buffer = b"vx=2.0,omega=1.0\n"
    runtime.step()
    after_velocity = dict(runtime._transport_car.last_cmd)

    assert ("handle_uart_line", "uart8", "x=12.0,angle=45.0") in events
    assert after_position["x"] == 12.0
    assert after_position["angle"] == 45.0
    assert "vx" not in after_position
    assert after_velocity == {"vx": 2.5, "vy": 0.5, "omega": 1.0}


def test_assistant_follow_runtime_velocity_write_keeps_rear_mode_state(
    monkeypatch,
) -> None:
    """rear 命令生效后，角色层速度写回要保住 rear_only_mode，并沿共享底盘速度入口执行。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"rear=1\nvx=1.0\n"
    uart6 = _FakeUart(["vx=0.5,vy=0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    runtime.step()

    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.5, "vy": 0.25, "omega": 0.0}
    assert runtime._transport_car.rear_only_mode is True
    assert runtime._transport_car.command_lock is False
    assert runtime._transport_car.command_mode == "none"
