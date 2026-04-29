"""辅车角色运行时入口与外观测试.

@file tests/unit/runtime/test_assistant_follow_runtime_public_api.py
"""

from .assistant_follow_runtime_support import (
    _FakeUart,
    import_assistant_module,
    install_counting_uart6_factory,
    install_counting_uart8_factory,
    install_fake_transport_car,
    install_fake_uart6_factory,
)


def test_assistant_follow_runtime_keeps_remote_control_surface(monkeypatch) -> None:
    """辅车角色运行时要保留启动壳依赖的对外外观."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime()
    ticker_obj = object()

    runtime.mark_tick(12)
    runtime.set_ticker(ticker_obj)

    assert runtime.wheel_states == [{"encoder": "enc-left"}, {"encoder": "enc-right"}]
    assert runtime.imu == "imu"
    assert hasattr(runtime, "step")
    assert events[:2] == [("mark_tick", 12), ("set_ticker", ticker_obj)]


def test_assistant_follow_runtime_initializes_uart6_before_control_cycle(
    monkeypatch,
) -> None:
    """UART6 初始化不应落在 step 控制周期里。"""

    install_fake_transport_car(monkeypatch)
    uart6_calls = []
    install_counting_uart6_factory(monkeypatch, _FakeUart(), uart6_calls)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    init_call_count = len(uart6_calls)

    assert init_call_count >= 1

    runtime.step()

    assert len(uart6_calls) == init_call_count


def test_assistant_follow_runtime_allows_uart8_injection_before_control_cycle(
    monkeypatch,
) -> None:
    """UART8 也要像 UART6 一样允许在构造阶段注入测试串口。"""

    install_fake_transport_car(monkeypatch)
    injected_uart8 = _FakeUart(["v,1.0,0.0"])
    install_fake_uart6_factory(monkeypatch, _FakeUart())
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(
        now_ms=lambda: 100, uart8=injected_uart8
    )

    runtime.step()

    assert runtime._transport_car.last_cmd == {"vx": 1.0, "vy": 0.0, "omega": 0.0}


def test_assistant_follow_runtime_initializes_uart8_before_control_cycle(
    monkeypatch,
) -> None:
    """UART8 初始化也不应落在 step 控制周期里。"""

    install_fake_transport_car(monkeypatch)
    uart8_calls = []
    install_counting_uart8_factory(monkeypatch, _FakeUart(), uart8_calls)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    init_call_count = len(uart8_calls)

    assert init_call_count >= 1

    runtime.step()

    assert len(uart8_calls) == init_call_count


def test_assistant_follow_runtime_step_runs_role_cycle_boundary(monkeypatch) -> None:
    """辅车角色运行时的 step 要先进入角色层周期边界再驱动共享底盘."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )
    runtime = follow_runtime_module.AssistantFollowRuntime()
    runtime._run_role_cycle = lambda: events.append("role_cycle")

    keep_running = runtime.step()

    assert keep_running is False
    assert events.index("role_cycle") < events.index("transport_step")


def test_assistant_follow_runtime_keeps_transport_uart3_processing_active(
    monkeypatch,
) -> None:
    """辅车角色层接管 UART8 后，不应顺手屏蔽共享底盘自己的 UART3 输入链。"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime()
    runtime._transport_car._process_uart()

    assert "transport_process_uart" in events


def test_assistant_package_entry_builds_follow_runtime(monkeypatch) -> None:
    """辅车包入口要继续给启动壳创建辅车角色运行时对象."""

    install_fake_transport_car(monkeypatch)
    assistant_module = import_assistant_module("vision.assistant", monkeypatch)

    runtime = assistant_module.create_transport_car()

    assert hasattr(runtime, "step")
    assert runtime.imu == "imu"
