"""辅车角色运行时诊断快照测试.

@file tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py
"""

from .assistant_follow_runtime_support import (
    _FakeUart,
    import_assistant_module,
    install_fake_transport_car,
    install_fake_uart6_factory,
)


def test_assistant_follow_runtime_exposes_follow_diagnostics_snapshot(
    monkeypatch,
) -> None:
    """辅车角色运行时要暴露当前生效速度和两路速度来源状态。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,2.0,0.0,1.0\n"
    uart6 = _FakeUart(["v,-0.5,0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert snapshot["state"] == "active"
    assert snapshot["transport_command"] == {"vx": 1.5, "vy": 0.25, "omega": 1.0}
    assert snapshot["uart6_input_status"] == "active"
    assert snapshot["uart8_input_status"] == "active"
    assert snapshot["uart6_velocity"] == {"vx": -0.5, "vy": 0.25, "omega": 0.0}
    assert snapshot["uart8_velocity"] == {"vx": 2.0, "vy": 0.0, "omega": 1.0}
    assert snapshot["last_error_text"] == "none"


def test_assistant_follow_runtime_keeps_feedforward_when_vision_is_missing(
    monkeypatch,
) -> None:
    """只有一路速度输入时，也要直接形成最终速度。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,2.0,-1.0,0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert runtime._transport_car.control_state == {"vx": 2.0, "vy": -1.0, "omega": 0.5}
    assert snapshot["state"] == "active"
    assert snapshot["transport_command"] == {"vx": 2.0, "vy": -1.0, "omega": 0.5}
    assert snapshot["uart6_input_status"] == "idle"
    assert snapshot["uart8_input_status"] == "active"


def test_assistant_follow_runtime_uses_vision_only_when_feedforward_is_missing(
    monkeypatch,
) -> None:
    """只有 UART6 一路速度输入时，也要能直接写回共享底盘入口。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b""
    uart6 = _FakeUart(["v,0.5,-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert ("handle_velocity", "assistant", 0.5, -0.25, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "assistant",
        "vx": 0.5,
        "vy": -0.25,
        "omega": 0.0,
        "has_omega": False,
    }
    assert runtime._transport_car.control_state == {"vx": 0.5, "vy": -0.25, "omega": 0.0}
    assert snapshot["state"] == "active"
    assert snapshot["transport_command"] == {"vx": 0.5, "vy": -0.25, "omega": 0.0}
    assert snapshot["uart6_input_status"] == "active"
    assert snapshot["uart8_input_status"] == "idle"


def test_assistant_follow_runtime_uses_feedforward_only_when_vision_is_missing(
    monkeypatch,
) -> None:
    """只有 UART8 一路速度输入时，也要能直接形成速度写回。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,-4.6,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert ("handle_velocity", "assistant", -4.6, 0.0, 0.0) in events
    assert runtime._transport_car.control_state == {"vx": -4.6, "vy": 0.0, "omega": 0.0}
    assert snapshot["transport_command"] == {"vx": -4.6, "vy": 0.0, "omega": 0.0}
    assert snapshot["uart6_input_status"] == "idle"
    assert snapshot["uart8_input_status"] == "active"


def test_assistant_follow_runtime_builds_diagnostics_snapshot_on_demand(
    monkeypatch,
) -> None:
    """控制周期不应每拍构造完整诊断快照，只有查询时才组织字典。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,2.0,0.0,1.0\n"
    uart6 = _FakeUart(["v,-0.5,0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    original_builder = follow_runtime_module.build_follow_snapshot
    build_calls = []

    def counting_builder(*args, **kwargs):
        build_calls.append((args, kwargs))
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        follow_runtime_module, "build_follow_snapshot", counting_builder
    )
    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    baseline_calls = len(build_calls)

    runtime.step()
    runtime.step()

    assert len(build_calls) == baseline_calls

    snapshot = runtime.build_follow_snapshot()

    assert len(build_calls) == baseline_calls + 1
    assert snapshot["transport_command"] == {"vx": 1.5, "vy": 0.25, "omega": 1.0}


def test_assistant_follow_runtime_snapshot_is_built_on_demand_only(
    monkeypatch,
) -> None:
    """双路速度输入模式下，控制周期不应额外构造诊断快照。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"v,1.0,0.0\n"
    uart6 = _FakeUart(["v,0.5,0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    build_calls = []
    original_builder = follow_runtime_module.build_follow_snapshot

    def counting_builder(*args, **kwargs):
        build_calls.append((args, kwargs))
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        follow_runtime_module, "build_follow_snapshot", counting_builder
    )
    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    baseline_calls = len(build_calls)

    runtime.step()
    runtime.step()

    assert len(build_calls) == baseline_calls

    snapshot = runtime.build_follow_snapshot()

    assert len(build_calls) == baseline_calls + 1
    assert snapshot["transport_command"] == {"vx": 1.5, "vy": 0.25, "omega": 0.0}


def test_assistant_follow_runtime_snapshot_exposes_idle_substate(monkeypatch) -> None:
    """idle 诊断要暴露当前子状态和清空后的速度缓存。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"s,12,0,0,0\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert snapshot["state"] == "idle"
    assert snapshot["assistant_state"] == 0
    assert snapshot["transport_command"] == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert snapshot["uart6_velocity"] == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert snapshot["uart8_velocity"] == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
