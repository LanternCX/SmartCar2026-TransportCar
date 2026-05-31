"""transport runtime 外观测试.

@file tests/unit/runtime/test_transport_runtime_surface.py
"""

from protocol.codec import (
    decode_assistant_vision_task_sync_body,
    encode_assistant_event_report_body,
    encode_assistant_state_sync_body,
    decode_velocity_body,
    encode_master_vision_event_report_body,
    encode_velocity_body,
)
from protocol.frame import decode_frame, encode_frame
from protocol.topic import (
    TOPIC_ASSISTANT_EVENT_REPORT,
    ROLE_ASSISTANT,
    ROLE_MASTER,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_ASSISTANT_VISION_TASK_SYNC,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_EVENT_REPORT,
    TOPIC_MASTER_VISION_HOOK_SYNC,
    UART6,
    UART8,
)
from protocol.transport import create_transport
from tests.unit.runtime.transport_runtime_support import (
    BufferedUart,
    ManualClock,
    ack_last_frame,
    import_module_clean,
    install_fake_core,
    run_runtime_cycle,
)


def test_master_runtime_exposes_external_transport_cycle(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart()
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8, now_ms=clock),
    )

    keep_running = run_runtime_cycle(runtime)

    assert keep_running is False
    assert hasattr(runtime, "poll_transport_rx")
    assert hasattr(runtime, "poll_transport_tx")
    frame = decode_frame(uart6.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_MASTER_VISION_HOOK_SYNC
    assert "transport_step" in cars[0].events


def test_master_runtime_applies_local_velocity_after_hook_delivery(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart()
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8, now_ms=clock),
    )

    run_runtime_cycle(runtime)
    uart6.push(ack_last_frame(uart6))
    clock.advance(20)
    run_runtime_cycle(runtime)
    uart6.push(
        encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(1.0, -2.0, 0.0, False),
        )
    )
    clock.advance(20)
    run_runtime_cycle(runtime)

    assert cars[0].last_chassis_target == {
        "source": "uart6",
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }
    forwarded = decode_frame(uart8.messages[-1])
    assert forwarded is not None
    assert forwarded["topic"] == TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
    assert decode_velocity_body(forwarded["body"][:7]) == {
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_clears_local_velocity_when_vision_event_arrives(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._active_hook_context_id = 7
    runtime._latest_uart6_velocity = {"vx": 1.0, "vy": -2.0, "omega": 0.0}
    cars[0].handle_velocity_packet(1.0, -2.0, 0.0, "uart6", False)

    runtime._handle_hook_event({"context_id": 7, "event": 6, "value": 9})

    assert runtime._latest_uart6_velocity is None
    assert cars[0].last_chassis_target == {
        "source": "master_vision_event",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_runtime_clears_local_velocity_when_assistant_event_arrives(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_ASSISTANT_EVENT_REPORT,
            7,
            encode_assistant_event_report_body(6, 9),
        )
    )
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=uart8,
            now_ms=clock,
        ),
    )
    runtime._latest_uart6_velocity = {"vx": 1.0, "vy": -2.0, "omega": 0.0}
    cars[0].handle_velocity_packet(1.0, -2.0, 0.0, "uart6", False)

    run_runtime_cycle(runtime)

    assert runtime._latest_uart6_velocity is None
    assert ("handle_velocity", "assistant_event", 0.0, 0.0, 0.0) in cars[0].events


def test_master_runtime_keeps_locked_pose_when_assistant_event_arrives(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_ASSISTANT_EVENT_REPORT,
            7,
            encode_assistant_event_report_body(6, 9),
        )
    )
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=uart8,
            now_ms=clock,
        ),
    )
    runtime._latest_uart6_velocity = {"vx": 1.0, "vy": -2.0, "omega": 0.0}
    cars[0].command_lock = True
    cars[0].control_state = {
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "x": 1.0,
        "y": 2.0,
        "angle": 90.0,
    }

    run_runtime_cycle(runtime)

    assert runtime._latest_uart6_velocity is None
    assert cars[0].command_lock is True
    assert cars[0].control_state["x"] == 1.0
    assert cars[0].control_state["y"] == 2.0
    assert ("handle_velocity", "assistant_event", 0.0, 0.0, 0.0) not in cars[0].events


def test_assistant_runtime_fuses_uart6_and_uart8_velocity(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(0.5, -0.25, 0.0, False),
        )
    )
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x01,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            0,
            encode_velocity_body(1.0, 0.0, 0.25, True),
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=uart8,
            now_ms=clock,
        ),
    )

    run_runtime_cycle(runtime)
    uart6.push(ack_last_frame(uart6))
    clock.advance(20)
    run_runtime_cycle(runtime)
    snapshot = runtime.build_follow_snapshot()

    assert cars[0].control_state == {"vx": 1.5, "vy": -0.25, "omega": 0.25}
    assert snapshot["state"] == "active"
    assert snapshot["assistant_state"] == module.ASSISTANT_STATE_FOLLOW
    assert snapshot["uart6_input_status"] == "active"
    assert snapshot["uart8_input_status"] == "active"


def test_assistant_runtime_announces_follow_to_local_vision_on_startup(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart()
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )

    run_runtime_cycle(runtime)

    frame = decode_frame(uart6.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_VISION_TASK_SYNC
    assert decode_assistant_vision_task_sync_body(frame["body"][:4]) == {
        "state": module.ASSISTANT_STATE_FOLLOW,
        "target": 0,
        "arg": 0,
    }


def test_assistant_runtime_treats_master_sync_as_zero_velocity(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(0.5, -0.25, 0.0, False),
        )
    )
    uart8 = BufferedUart(
        incoming=(
            encode_frame(
                0x01,
                TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
                0,
                encode_velocity_body(1.0, 0.0, 0.25, True),
            )
            + encode_frame(
                0x02,
                TOPIC_ASSISTANT_STATE_SYNC,
                7,
                encode_assistant_state_sync_body(
                    module.ASSISTANT_STATE_APPROACH_OBJECT,
                    module.ASSISTANT_TARGET_OBJECT,
                    1,
                ),
            )
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=uart8,
            now_ms=clock,
        ),
    )

    run_runtime_cycle(runtime)

    assert runtime._uart6_velocity is None
    assert runtime._uart8_velocity is None
    assert cars[0].last_chassis_target == {
        "source": "assistant_approach_object",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_runtime_cycle_requests_each_port_once_for_normal_input(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(0.5, -0.25, 0.0, False),
        )
    )
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x01,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            0,
            encode_velocity_body(1.0, 0.0, 0.25, True),
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=uart8,
            now_ms=clock,
        ),
    )

    run_runtime_cycle(runtime)

    assert uart6.any_calls == 1
    assert uart6.read_calls == 1
    assert uart8.any_calls == 1
    assert uart8.read_calls == 1


def test_master_runtime_cycle_requests_each_port_once_for_normal_input(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(0.5, -0.25, 0.0, False),
        )
    )
    uart8 = BufferedUart(
        incoming=encode_frame(0x02, TOPIC_ASSISTANT_EVENT_REPORT, 7, bytes([6, 0, 9]))
    )
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=uart6,
            uart8=uart8,
            now_ms=clock,
        ),
    )

    run_runtime_cycle(runtime)

    assert uart6.any_calls == 1
    assert uart6.read_calls == 1
    assert uart8.any_calls == 1
    assert uart8.read_calls == 1


def test_master_runtime_logs_when_camera_sync_is_blocked_before_first_send(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    logs = []
    monkeypatch.setattr(module, "log", lambda stage, detail="": logs.append((stage, detail)))
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_MASTER_VISION_EVENT_REPORT,
            7,
            encode_master_vision_event_report_body(99, 6, 1),
        )
    )
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=uart6,
            uart8=uart8,
            now_ms=clock,
        ),
    )

    run_runtime_cycle(runtime)

    assert any(
        stage == "sync"
        and "master->camera sync blocked status=dropped_priority" in detail
        for stage, detail in logs
    )


def test_master_runtime_logs_role_cycle_failure_to_board_log(capsys, monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )

    def _raise_role_cycle():
        raise RuntimeError("boom")

    runtime._run_role_cycle = _raise_role_cycle

    keep_running = run_runtime_cycle(runtime)
    output = capsys.readouterr().out

    assert keep_running is False
    assert "master_error: master role cycle failed: boom" in output
    assert "master_error: traceback start" in output
    assert "master_error: traceback end" in output
    assert cars[0].last_exception_text == "master role cycle failed: boom"


def test_master_runtime_reports_role_cycle_failure_via_full_trace_helper(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    calls = []
    monkeypatch.setattr(
        module,
        "log_exception",
        lambda stage, detail, exc: calls.append((stage, detail, str(exc))),
        raising=False,
    )
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )

    runtime._run_role_cycle = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    run_runtime_cycle(runtime)

    assert calls == [("master_error", "master role cycle failed: boom", "boom")]


def test_master_runtime_calls_state_machine_step_without_keyword_args(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    logs = []
    monkeypatch.setattr(module, "log", lambda stage, detail="": logs.append((stage, detail)))
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    calls = []

    def _positional_step(*args, **kwargs):
        assert kwargs == {}
        calls.append(bool(args[0]))

    runtime._state_machine.step = _positional_step

    keep_running = run_runtime_cycle(runtime)

    assert keep_running is False
    assert calls == [False]
    assert not any(stage == "master_error" for stage, _ in logs)


def test_master_runtime_calls_handle_event_without_keyword_args(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    calls = []

    def _positional_handle_event(*args, **kwargs):
        assert kwargs == {}
        calls.append(args)

    runtime._state_machine.handle_event = _positional_handle_event
    runtime._active_hook_context_id = 7

    runtime._handle_hook_event({"context_id": 7, "event": 6, "value": 9})

    assert calls == [(7, 6, 9)]


def test_master_runtime_calls_transport_velocity_api_without_keyword_args(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    calls = []

    def _positional_handle_velocity(*args, **kwargs):
        assert kwargs == {}
        calls.append(args)

    cars[0].handle_velocity_packet = _positional_handle_velocity
    runtime._latest_uart6_velocity = {"vx": 1.0, "vy": -2.0}

    runtime._apply_latest_uart6_velocity()

    assert calls == [(1.0, -2.0, 0.0, "uart6", False)]


def test_master_runtime_return_retreat_uses_fixed_reverse_speed(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_RETURN_GARAGE_RETREAT
    runtime._latest_uart6_velocity = {"vx": 9.0, "vy": 8.0}

    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": "master_return_retreat",
        "vx": 0.0,
        "vy": module.MASTER_RETURN_GARAGE_RETREAT_SPEED,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_return_line_combines_fixed_left_and_yellow_line_y(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_RETURN_GARAGE_LINE
    runtime._latest_uart6_velocity = {"vx": 9.0, "vy": -1.25}

    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": "master_return_line",
        "vx": module.MASTER_RETURN_GARAGE_LEFT_SPEED,
        "vy": -1.25,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_return_marker_uses_marker_velocity_and_finished_stops(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_RETURN_GARAGE_MARKER
    runtime._latest_uart6_velocity = {"vx": 1.5, "vy": -0.5}

    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": "master_return_marker",
        "vx": 1.5,
        "vy": -0.5,
        "omega": 0.0,
        "has_omega": False,
    }

    runtime._state_machine.state = module.STATE_FINISHED
    runtime._latest_uart6_velocity = {"vx": 2.0, "vy": 2.0}

    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": "master_finished",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_reports_role_cycle_failure_via_full_trace_helper(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    calls = []
    monkeypatch.setattr(
        module,
        "log_exception",
        lambda stage, detail, exc: calls.append((stage, detail, str(exc))),
        raising=False,
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )

    runtime._run_role_cycle = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    run_runtime_cycle(runtime)

    assert calls == [("assistant_error", "role_cycle failed: boom", "boom")]


def test_assistant_runtime_return_follow_uses_normal_follow_velocity_fusion(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._uart6_velocity = {"vx": 1.0, "vy": 2.0, "omega": 0.0, "has_omega": False}
    runtime._uart8_velocity = {"vx": -0.5, "vy": 3.0, "omega": 0.25, "has_omega": True}

    runtime._write_effective_velocity()

    assert cars[0].last_chassis_target == {
        "source": "assistant",
        "vx": 0.5,
        "vy": 5.0,
        "omega": 0.25,
        "has_omega": True,
    }


def test_assistant_runtime_finished_sync_clears_inputs_and_stops(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._uart6_velocity = {"vx": 1.0, "vy": 2.0, "omega": 0.0, "has_omega": False}
    runtime._uart8_velocity = {"vx": 3.0, "vy": 4.0, "omega": 0.0, "has_omega": False}

    accepted = runtime._apply_sync_context(
        {"state": module.ASSISTANT_STATE_FINISHED, "target": 0, "arg": 0}
    )

    assert accepted is True
    assert runtime._uart6_velocity is None
    assert runtime._uart8_velocity is None
    assert cars[0].last_chassis_target == {
        "source": "assistant_finished",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }
