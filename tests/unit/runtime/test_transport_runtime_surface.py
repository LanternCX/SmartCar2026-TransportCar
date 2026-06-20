"""transport runtime 外观测试.

@file tests/unit/runtime/test_transport_runtime_surface.py
"""

from protocol.codec import (
    LOCAL_VISION_CONTROL_PAUSE,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    LOCAL_VISION_CONTROL_RESUME,
    decode_local_vision_control_body,
    decode_assistant_state_sync_body,
    decode_assistant_vision_task_sync_body,
    encode_local_vision_control_body,
    encode_assistant_vision_event_report_body,
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
    TOPIC_ASSISTANT_VISION_EVENT_REPORT,
    TOPIC_ASSISTANT_VISION_TASK_SYNC,
    TOPIC_LOCAL_VISION_CONTROL,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_EVENT_REPORT,
    TOPIC_MASTER_VISION_TASK_SYNC,
    UART6,
    UART8,
)
from protocol.transport import create_transport
from play.routines.assistant_return_garage import ASSISTANT_LEAD_DISTANCE
from play.routines.master_return_garage import MASTER_LEAD_DISTANCE
from tests.unit.runtime.transport_runtime_support import (
    BufferedUart,
    ManualClock,
    ack_last_frame,
    import_module_clean,
    install_fake_core,
    run_runtime_cycle,
)


def _pack_task_arg(config_id, object_id):
    packed = (int(config_id) & 0xFF) | ((int(object_id) & 0xFF) << 8)
    if packed >= 0x8000:
        packed -= 0x10000
    return packed


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
    assert frame["topic"] == TOPIC_MASTER_VISION_TASK_SYNC
    assert "transport_step" in cars[0].events


def test_master_runtime_applies_local_velocity_after_task_delivery(monkeypatch) -> None:
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
    runtime._active_task_context_id = 7
    runtime._latest_uart6_velocity = {"vx": 1.0, "vy": -2.0, "omega": 0.0}
    cars[0].handle_velocity_packet(1.0, -2.0, 0.0, "uart6", False)

    runtime._handle_task_event({"context_id": 7, "event": 6, "value": 9})

    assert runtime._latest_uart6_velocity is None
    assert cars[0].last_chassis_target == {
        "source": "master_vision_event",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_runtime_logs_when_task_event_arrives(monkeypatch, capsys) -> None:
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

    runtime._handle_task_event({"context_id": 7, "event": 8, "value": 0})

    captured = capsys.readouterr().out
    assert "master_event: received context=7 event=8 value=0" in captured


def test_master_runtime_forwards_target_threshold_to_assistant(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("vision.master.state_machine", monkeypatch)
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=uart8,
            now_ms=clock,
        ),
    )
    threshold = (12, 80, -30, 40, -20, 60)
    runtime._state_machine.state = module.STATE_SEARCH_OBJECT
    runtime._active_task_context_id = int(runtime._state_machine._current_context_id)

    runtime._handle_task_event(
        {
            "context_id": int(runtime._state_machine._current_context_id),
            "event": module.EVENT_TARGET_FOUND,
            "value": 2,
            "threshold": threshold,
        }
    )
    runtime._drain_state_machine_outputs()
    runtime._queue_pending_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart8.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_STATE_SYNC
    assert decode_assistant_state_sync_body(frame["body"][:10]) == {
        "state": state_module.ASSISTANT_OBJECT_SYNC_STATE,
        "target": state_module.ASSISTANT_OBJECT_SYNC_TARGET,
        "arg": _pack_task_arg(module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID, 2),
        "threshold": threshold,
    }


def test_master_runtime_encodes_latest_threshold_when_sending_assistant_sync(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("vision.master.state_machine", monkeypatch)
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=uart8,
            now_ms=clock,
        ),
    )
    old_threshold = (10, 70, -20, 30, -10, 50)
    latest_threshold = (12, 80, -30, 40, -20, 60)
    runtime._current_object_threshold = latest_threshold
    runtime._pending_assistant_sync = {
        "kind": "assistant_object",
        "state": state_module.ASSISTANT_OBJECT_SYNC_STATE,
        "target": state_module.ASSISTANT_OBJECT_SYNC_TARGET,
        "arg": _pack_task_arg(module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID, 2),
        "threshold": old_threshold,
        "queued": False,
    }

    runtime._queue_pending_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart8.messages[-1])
    assert frame is not None
    assert decode_assistant_state_sync_body(frame["body"][:10])["threshold"] == latest_threshold


def test_master_runtime_pauses_local_vision_control_from_reliable_packet(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_LOCAL_VISION_CONTROL,
            9,
            encode_local_vision_control_body(LOCAL_VISION_CONTROL_PAUSE),
        )
    )
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_SEARCH_OBJECT
    runtime._latest_uart6_velocity = {"vx": 1.0, "vy": -2.0, "omega": 0.0}
    cars[0].handle_velocity_packet(1.0, -2.0, 0.0, "uart6", False)

    run_runtime_cycle(runtime)

    assert runtime._local_vision_control_paused is True
    assert runtime._latest_uart6_velocity is None
    assert cars[0].last_chassis_target == {
        "source": "local_vision_pause",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }
    ack_frame = decode_frame(uart6.messages[-1])
    assert ack_frame is not None
    assert ack_frame["mode"] == 0x03
    assert ack_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL


def test_master_runtime_ignores_stale_pause_after_entering_transport(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_LOCAL_VISION_CONTROL,
            9,
            encode_local_vision_control_body(LOCAL_VISION_CONTROL_PAUSE),
        )
    )
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_TRANSPORT_OBJECT

    run_runtime_cycle(runtime)

    assert runtime._local_vision_control_paused is False
    assert cars[0].last_chassis_target == {
        "source": "master_transport",
        "vx": 0.0,
        "vy": module.TRANSPORT_FORWARD_SPEED,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_resume_discards_cached_velocity_until_next_udp(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=(
            encode_frame(
                0x02,
                TOPIC_LOCAL_VISION_CONTROL,
                9,
                encode_local_vision_control_body(LOCAL_VISION_CONTROL_RESUME),
            )
            + encode_frame(
                0x01,
                TOPIC_LOCAL_VISION_VELOCITY,
                0,
                encode_velocity_body(2.0, 3.0, 0.0, False),
            )
        )
    )
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_SEARCH_OBJECT
    runtime._local_vision_control_paused = True

    run_runtime_cycle(runtime)

    assert runtime._local_vision_control_paused is False
    assert runtime._latest_uart6_velocity is None
    assert cars[0].last_chassis_target["source"] is None

    uart6.push(
        encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(2.0, 3.0, 0.0, False),
        )
    )
    clock.advance(20)
    run_runtime_cycle(runtime)

    assert cars[0].last_chassis_target == {
        "source": "uart6",
        "vx": 2.0,
        "vy": 3.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_transport_transition_clears_local_vision_pause(monkeypatch) -> None:
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
    runtime._local_vision_control_paused = True
    runtime._latest_uart6_velocity = {"vx": 1.5, "vy": -0.5, "omega": 0.0}
    runtime._state_machine.state = module.STATE_SEARCH_OBJECT
    runtime._last_role_state = module.STATE_SEARCH_OBJECT

    runtime._state_machine.state = module.STATE_TRANSPORT_OBJECT

    runtime._run_role_cycle()

    assert runtime._local_vision_control_paused is False
    assert cars[0].last_chassis_target == {
        "source": "master_transport",
        "vx": 0.0,
        "vy": module.TRANSPORT_FORWARD_SPEED,
        "omega": 0.0,
        "has_omega": False,
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
    runtime.poll_transport_tx()
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
    runtime._queue_pending_local_vision_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart6.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_VISION_TASK_SYNC
    assert decode_assistant_vision_task_sync_body(frame["body"][:10]) == {
        "state": module.ASSISTANT_STATE_FOLLOW,
        "target": 0,
        "arg": 0,
        "threshold": (0, 0, 0, 0, 0, 0),
    }


def test_assistant_runtime_forwards_master_threshold_to_local_vision(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    threshold = (12, 80, -30, 40, -20, 60)
    uart6 = BufferedUart()
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_ASSISTANT_STATE_SYNC,
            7,
            encode_assistant_state_sync_body(
                module.ASSISTANT_STATE_APPROACH_OBJECT,
                module.ASSISTANT_TARGET_OBJECT,
                _pack_task_arg(1, 2),
                threshold,
            ),
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
    runtime._queue_pending_local_vision_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart6.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_VISION_TASK_SYNC
    assert decode_assistant_vision_task_sync_body(frame["body"][:10]) == {
        "state": module.ASSISTANT_STATE_APPROACH_OBJECT,
        "target": module.ASSISTANT_TARGET_OBJECT,
        "arg": _pack_task_arg(1, 2),
        "threshold": threshold,
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
                    _pack_task_arg(1, 2),
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
    assert runtime._pending_local_vision_sync == {
        "state": module.ASSISTANT_STATE_APPROACH_OBJECT,
        "target": module.ASSISTANT_TARGET_OBJECT,
        "arg": _pack_task_arg(1, 2),
        "threshold": (0, 0, 0, 0, 0, 0),
        "queued": False,
    }
    assert cars[0].last_chassis_target == {
        "source": "assistant_approach_object",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_pauses_chassis_from_local_vision_control(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_LOCAL_VISION_CONTROL,
            9,
            encode_local_vision_control_body(LOCAL_VISION_CONTROL_PAUSE),
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._uart6_velocity = {"vx": 1.0, "vy": 2.0, "omega": 0.0, "has_omega": False}
    runtime._uart8_velocity = {"vx": 3.0, "vy": 4.0, "omega": 0.0, "has_omega": False}
    cars[0].handle_velocity_packet(4.0, 6.0, 0.0, "assistant", False)

    run_runtime_cycle(runtime)

    assert runtime._local_vision_control_paused is True
    assert runtime._uart6_velocity is None
    assert runtime._uart8_velocity is None
    assert cars[0].last_chassis_target == {
        "source": "local_vision_pause",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }
    ack_frame = decode_frame(uart6.messages[-1])
    assert ack_frame is not None
    assert ack_frame["mode"] == 0x03
    assert ack_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL


def test_assistant_runtime_ignores_stale_pause_after_entering_transport(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_LOCAL_VISION_CONTROL,
            9,
            encode_local_vision_control_body(LOCAL_VISION_CONTROL_PAUSE),
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.ASSISTANT_STATE_TRANSPORT_OBJECT
    runtime._uart8_velocity = {"vx": 0.0, "vy": 4.0, "omega": 0.0, "has_omega": False}

    run_runtime_cycle(runtime)

    assert runtime._local_vision_control_paused is False
    feedforward_scale = module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE
    assert cars[0].last_chassis_target == {
        "source": "assistant",
        "vx": 0.0,
        "vy": -4.0 * feedforward_scale,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_runtime_ignores_pause_during_return_follow_play(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_LOCAL_VISION_CONTROL,
            9,
            encode_local_vision_control_body(LOCAL_VISION_CONTROL_PAUSE),
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._pending_local_vision_sync = None

    run_runtime_cycle(runtime)

    assert runtime._local_vision_control_paused is False
    assert runtime.play.current_play is not None
    assert (
        "set_relative_translation_target",
        0.0,
        ASSISTANT_LEAD_DISTANCE,
    ) in cars[0].events


def test_assistant_runtime_resume_discards_cached_velocity_until_next_udp(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=(
            encode_frame(
                0x02,
                TOPIC_LOCAL_VISION_CONTROL,
                9,
                encode_local_vision_control_body(LOCAL_VISION_CONTROL_RESUME),
            )
            + encode_frame(
                0x01,
                TOPIC_LOCAL_VISION_VELOCITY,
                0,
                encode_velocity_body(2.0, 3.0, 0.0, False),
            )
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._local_vision_control_paused = True
    runtime._pending_local_vision_sync = None

    run_runtime_cycle(runtime)

    assert runtime._local_vision_control_paused is False
    assert runtime._uart6_velocity is None
    assert cars[0].last_chassis_target["source"] is None

    uart6.push(
        encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(2.0, 3.0, 0.0, False),
        )
    )
    clock.advance(20)
    run_runtime_cycle(runtime)

    assert cars[0].last_chassis_target == {
        "source": "assistant",
        "vx": 2.0,
        "vy": 3.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_runtime_new_sync_clears_local_vision_pause(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
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
    runtime._local_vision_control_paused = True

    accepted = runtime._apply_sync_context(
        {
            "state": module.ASSISTANT_STATE_TRANSPORT_OBJECT,
            "target": module.ASSISTANT_TARGET_OBJECT,
            "arg": _pack_task_arg(2, 1),
        }
    )

    assert accepted is True
    assert runtime._local_vision_control_paused is False


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
    runtime._active_task_context_id = 7

    runtime._handle_task_event({"context_id": 7, "event": 6, "value": 9})

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


def test_master_runtime_return_retreat_starts_play_with_lead_translation(monkeypatch) -> None:
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

    runtime._apply_motion_outputs()

    assert runtime.play.current_play is not None
    assert (
        "set_relative_translation_target",
        0.0,
        MASTER_LEAD_DISTANCE,
    ) in cars[0].events


def test_master_runtime_final_clear_retreat_enters_return_and_queues_assistant_sync(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("vision.master.state_machine", monkeypatch)
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=uart8,
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_CLEAR_OBJECT
    runtime._state_machine._clear_phase = module.CLEAR_PHASE_RETREAT
    runtime._state_machine._required_object_count = 1
    runtime._state_machine._master_cleared = True
    runtime._state_machine.handle_assistant_cleared(value=module.CLEAR_PHASE_RETREAT)

    runtime._drain_state_machine_outputs()
    runtime._queue_pending_sync()
    runtime._queue_pending_task_sync()
    runtime.poll_transport_tx()
    runtime.poll_transport_tx()

    assert runtime._state_machine.state == module.STATE_RETURN_GARAGE_RETREAT
    frame = decode_frame(uart8.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_STATE_SYNC
    assert frame["body"][:10] == encode_assistant_state_sync_body(
        state_module.ASSISTANT_RETURN_FOLLOW_SYNC_STATE,
        state_module.ASSISTANT_RETURN_FOLLOW_SYNC_TARGET,
        0,
    )


def test_master_runtime_turn_back_completes_immediately_after_lock_release(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("vision.master.state_machine", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_CLEAR_OBJECT
    runtime._state_machine._clear_phase = state_module._CLEAR_STAGE_TURN_BACK
    runtime._state_machine._required_object_count = 1
    runtime._turn_back_rotation_started = True
    cars[0].command_lock = False
    for state in cars[0].wheel_states:
        state["filtered_speed"] = float(module.MOTION_STOP_SPEED_THRESHOLD) + 1.0

    runtime._run_turn_back_phase()
    runtime._drain_state_machine_outputs()

    assert runtime._turn_back_rotation_started is False
    assert runtime._state_machine.state == module.STATE_RETURN_GARAGE_RETREAT


def test_master_runtime_turn_back_completes_inside_turn_back_tolerance(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("vision.master.state_machine", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_CLEAR_OBJECT
    runtime._state_machine._clear_phase = state_module._CLEAR_STAGE_TURN_BACK
    runtime._state_machine._required_object_count = 1
    runtime._turn_back_rotation_started = True
    target_heading_deg = 180.0
    tolerance_deg = float(module.MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG)
    runtime._turn_back_target_heading_deg = target_heading_deg
    cars[0].heading_est = target_heading_deg - tolerance_deg + 0.1
    cars[0].command_lock = True

    runtime._run_turn_back_phase()
    runtime._drain_state_machine_outputs()

    assert runtime._turn_back_rotation_started is False
    assert runtime._state_machine.state == module.STATE_RETURN_GARAGE_RETREAT
    assert (
        "handle_velocity",
        "master_turn_back_tolerance",
        0.0,
        0.0,
        0.0,
    ) in cars[0].events


def test_master_runtime_turn_back_keeps_waiting_outside_turn_back_tolerance(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("vision.master.state_machine", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_CLEAR_OBJECT
    runtime._state_machine._clear_phase = state_module._CLEAR_STAGE_TURN_BACK
    runtime._state_machine._required_object_count = 1
    runtime._turn_back_rotation_started = True
    target_heading_deg = 180.0
    tolerance_deg = float(module.MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG)
    runtime._turn_back_target_heading_deg = target_heading_deg
    cars[0].heading_est = target_heading_deg - tolerance_deg - 0.1
    cars[0].command_lock = True

    runtime._run_turn_back_phase()
    runtime._drain_state_machine_outputs()

    assert runtime._turn_back_rotation_started is True
    assert runtime._state_machine.state == module.STATE_CLEAR_OBJECT


def test_master_runtime_return_play_reaches_hold_velocity_after_yellow_ready(monkeypatch) -> None:
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
    runtime._state_machine.state = module.STATE_RETURN_GARAGE_RETREAT
    runtime._apply_motion_outputs()
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    cars[0].heading_est = 90.0
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    assert cars[0].last_chassis_target == {
        "source": "master_play",
        "vx": 0.0,
        "vy": 5.0,
        "omega": 0.0,
        "has_omega": False,
    }
    runtime._return_line_aligned = True
    runtime._apply_motion_outputs()
    cars[0].heading_est = 90.0
    runtime._apply_motion_outputs()
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()

    assert ("set_heading_transition_target", 0.0) in cars[0].events
    assert cars[0].last_chassis_target == {
        "source": "master_play",
        "vx": 0.0,
        "vy": 3.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_clears_stale_yellow_ready_when_entering_forward_step(monkeypatch) -> None:
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
    runtime._return_line_aligned = True

    runtime._apply_motion_outputs()
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    cars[0].heading_est = 90.0
    cars[0].command_lock = False

    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()

    assert runtime._return_line_aligned is False
    assert runtime.play.current_play is not None
    assert runtime.play.current_play.step_index == 2
    assert cars[0].last_chassis_target == {
        "source": "master_play",
        "vx": 0.0,
        "vy": 5.0,
        "omega": 0.0,
        "has_omega": False,
    }

    runtime._return_line_aligned = True
    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": "master_play",
        "vx": 0.0,
        "vy": 5.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_step_two_queues_return_line_gate_on_and_off(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=uart6,
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._state_machine.state = module.STATE_RETURN_GARAGE_RETREAT

    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()
    runtime._transport_car.command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()
    runtime._transport_car.heading_est = 90.0
    runtime._transport_car.command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()

    gate_on_frame = decode_frame(uart6.messages[-1])
    assert gate_on_frame is not None
    assert gate_on_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL
    assert decode_local_vision_control_body(gate_on_frame["body"]) == {
        "action": LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    }
    uart6.push(ack_last_frame(uart6))
    runtime.poll_transport_rx()
    runtime._check_transport_deliveries()

    runtime._return_line_aligned = True
    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()

    gate_off_frame = decode_frame(uart6.messages[-1])
    assert gate_off_frame is not None
    assert gate_off_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL
    assert decode_local_vision_control_body(gate_off_frame["body"]) == {
        "action": LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
    }


def test_master_runtime_does_not_expose_return_marker_motion_state(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )

    assert not hasattr(module, "STATE_RETURN_GARAGE_MARKER")


def test_master_runtime_finished_stops_without_consuming_local_velocity(monkeypatch) -> None:
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


def test_assistant_runtime_return_follow_starts_play_with_left_turn(
    monkeypatch,
) -> None:
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
    runtime._pending_local_vision_sync = None

    runtime._write_effective_velocity()

    assert runtime.play.current_play is not None
    assert (
        "set_relative_translation_target",
        0.0,
        ASSISTANT_LEAD_DISTANCE,
    ) in cars[0].events
    cars[0].command_lock = False
    cars[0].heading_est = 0.0
    runtime._write_effective_velocity()
    runtime._write_effective_velocity()
    assert ("set_heading_transition_target", -90.0) in cars[0].events


def test_assistant_runtime_step_two_queues_return_line_gate_on(monkeypatch) -> None:
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
    runtime._state_machine.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._pending_local_vision_sync = None

    runtime._write_effective_velocity()
    runtime._queue_return_line_gate_action()
    runtime.poll_transport_tx()
    runtime._transport_car.command_lock = False
    runtime._write_effective_velocity()
    runtime._write_effective_velocity()
    runtime._transport_car.heading_est = -90.0
    runtime._transport_car.command_lock = False
    runtime._write_effective_velocity()
    runtime._write_effective_velocity()
    runtime._queue_return_line_gate_action()
    runtime.poll_transport_tx()

    gate_on_frame = decode_frame(uart6.messages[-1])
    assert gate_on_frame is not None
    assert gate_on_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL
    assert decode_local_vision_control_body(gate_on_frame["body"]) == {
        "action": LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    }


def test_assistant_transport_discards_feedforward_x_and_scales_feedforward_y(
    monkeypatch,
) -> None:
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
    runtime._state_machine.state = module.ASSISTANT_STATE_TRANSPORT_OBJECT
    runtime._pending_local_vision_sync = None
    runtime._uart6_velocity = {"vx": 1.0, "vy": 2.0, "omega": 0.0, "has_omega": False}
    runtime._uart8_velocity = {"vx": 3.0, "vy": 4.0, "omega": 0.0, "has_omega": False}

    runtime._write_effective_velocity()

    feedforward_scale = module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE
    assert cars[0].last_chassis_target == {
        "source": "assistant",
        "vx": 1.0,
        "vy": 2.0 - 4.0 * feedforward_scale,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_runtime_transport_syncs_local_transport_object_task(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
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

    accepted = runtime._apply_sync_context(
        {
            "state": module.ASSISTANT_STATE_TRANSPORT_OBJECT,
            "target": module.ASSISTANT_TARGET_OBJECT,
            "arg": _pack_task_arg(2, 1),
        }
    )

    assert accepted is True
    assert runtime._pending_local_vision_sync == {
        "state": module.ASSISTANT_STATE_TRANSPORT_OBJECT,
        "target": module.ASSISTANT_TARGET_OBJECT,
        "arg": _pack_task_arg(module._ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID, 1),
        "threshold": (0, 0, 0, 0, 0, 0),
        "queued": False,
    }


def test_assistant_runtime_return_follow_syncs_local_yellow_line_task(monkeypatch) -> None:
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

    accepted = runtime._apply_sync_context(
        {"state": module.ASSISTANT_STATE_RETURN_FOLLOW, "target": 0, "arg": 0}
    )

    assert accepted is True
    assert runtime._pending_local_vision_sync == {
        "state": module.ASSISTANT_STATE_RETURN_FOLLOW,
        "target": 0,
        "arg": module.ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID,
        "threshold": (0, 0, 0, 0, 0, 0),
        "queued": False,
    }
    assert cars[0].last_chassis_target == {
        "source": "assistant_return_play",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_return_follow_sync_uses_standard_logs(capsys, monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_ASSISTANT_STATE_SYNC,
            7,
            encode_assistant_state_sync_body(
                module.ASSISTANT_STATE_RETURN_FOLLOW,
                0,
                0,
            ),
        )
    )
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=uart8,
            now_ms=clock,
        ),
    )

    run_runtime_cycle(runtime)

    output = capsys.readouterr().out
    assert "assistant_state: RETURN_FOLLOW\n" in output
    assert "sync: master->assistant sync done state=6 target=0 arg=0\n" in output
    assert "assistant_return:" not in output


def test_assistant_runtime_return_follow_event_only_marks_alignment(monkeypatch) -> None:
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
    runtime._state_machine.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._pending_local_vision_sync = None
    uart6.push(
        encode_frame(
            0x02,
            TOPIC_ASSISTANT_VISION_EVENT_REPORT,
            9,
            encode_assistant_vision_event_report_body(
                10,
                0,
            ),
        )
    )

    run_runtime_cycle(runtime)

    assert runtime._state_machine.state == module.ASSISTANT_STATE_RETURN_FOLLOW
    assert runtime._return_line_aligned is True


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
