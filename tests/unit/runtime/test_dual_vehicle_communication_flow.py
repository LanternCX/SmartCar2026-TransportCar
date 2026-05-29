"""双车通信状态圈测试.

@file tests/unit/runtime/test_dual_vehicle_communication_flow.py
"""

from protocol.codec import (
    encode_assistant_state_sync_body,
    encode_assistant_vision_event_report_body,
    encode_master_vision_event_report_body,
)
from protocol.frame import decode_frame, encode_frame
from protocol.topic import (
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_STATE_SYNC,
    ROLE_ASSISTANT,
    ROLE_MASTER,
    TOPIC_ASSISTANT_VISION_EVENT_REPORT,
    TOPIC_MASTER_VISION_EVENT_REPORT,
    UART8,
)
from protocol.transport import create_transport
from tests.unit.runtime.transport_runtime_support import (
    BufferedUart,
    ManualClock,
    ack_last_frame,
    import_module_clean,
    install_fake_core,
    make_linked_uart_pair,
    run_runtime_cycle,
)


def _ack_latest_tcp_if_needed(uart):
    if not uart.messages:
        return
    frame = decode_frame(uart.messages[-1])
    assert frame is not None
    if frame["mode"] != 0x02:
        return
    uart.push(ack_last_frame(uart))


def _pump_pair(clock, master, assistant, master_car, assistant_car, master_uart6, assistant_uart6, steps=1):
    for _ in range(steps):
        run_runtime_cycle(master)
        _ack_latest_tcp_if_needed(master_uart6)
        run_runtime_cycle(assistant)
        _ack_latest_tcp_if_needed(assistant_uart6)
        if master._state_machine.state == 2 and master_car.command_lock:
            master_car.command_lock = False
        if assistant._state_machine.state == 3 and assistant_car.command_lock:
            assistant_car.command_lock = False
        if master._state_machine.state == 5 and master_car.command_lock:
            master_car.command_lock = False
        if assistant._state_machine.state == 5 and assistant_car.command_lock:
            assistant_car.command_lock = False
        clock.advance(20)


def _pump_until(clock, master, assistant, master_car, assistant_car, master_uart6, assistant_uart6, condition, max_steps=80):
    for _ in range(max_steps):
        if condition():
            return
        _pump_pair(clock, master, assistant, master_car, assistant_car, master_uart6, assistant_uart6)
    raise AssertionError("condition not reached")


def test_master_and_assistant_complete_full_state_loop(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    master_module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    assistant_module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)

    master_uart6 = BufferedUart()
    assistant_uart6 = BufferedUart()
    master_uart8, assistant_uart8 = make_linked_uart_pair()

    master = master_module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=master_uart6,
            uart8=master_uart8,
            now_ms=clock,
        ),
    )
    assistant = assistant_module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=assistant_uart6,
            uart8=assistant_uart8,
            now_ms=clock,
        ),
    )
    master_car = cars[0]
    assistant_car = cars[1]

    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: master._active_hook_context_id is not None,
    )

    master_uart6.push(
        encode_frame(
            0x02,
            TOPIC_MASTER_VISION_EVENT_REPORT,
            1,
            encode_master_vision_event_report_body(
                master._active_hook_context_id,
                master_module.EVENT_TARGET_FOUND,
                300,
            ),
        )
    )
    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: master._state_machine.state == master_module.STATE_ORBITING,
    )

    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: assistant._state_machine.state == assistant_module.ASSISTANT_STATE_APPROACH_OBJECT
        and assistant._pending_local_vision_sync is None,
    )

    assistant_uart6.push(
        encode_frame(
            0x02,
            TOPIC_ASSISTANT_VISION_EVENT_REPORT,
            1,
            encode_assistant_vision_event_report_body(
                assistant_module._TARGET_FOUND_EVENT,
                300,
            ),
        )
    )
    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: assistant._state_machine.state == assistant_module.ASSISTANT_STATE_ORBIT,
    )

    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: assistant._post_orbit_realign_active
        and assistant._state_machine.state == assistant_module.ASSISTANT_STATE_APPROACH_OBJECT
        and assistant._pending_local_vision_sync is None,
    )

    master_uart6.push(
        encode_frame(
            0x02,
            TOPIC_MASTER_VISION_EVENT_REPORT,
            2,
            encode_master_vision_event_report_body(
                master._active_hook_context_id,
                master_module.EVENT_ALIGNED,
                0,
            ),
        )
    )
    assistant_uart6.push(
        encode_frame(
            0x02,
            TOPIC_ASSISTANT_VISION_EVENT_REPORT,
            2,
            encode_assistant_vision_event_report_body(
                assistant_module._ALIGNED_EVENT,
                0,
            ),
        )
    )
    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: master._state_machine.state == master_module.STATE_TRANSPORT_OBJECT
        and assistant._state_machine.state == assistant_module.ASSISTANT_STATE_TRANSPORT_OBJECT,
    )
    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: master._active_hook_context_id is not None,
    )

    master_uart6.push(
        encode_frame(
            0x02,
            TOPIC_MASTER_VISION_EVENT_REPORT,
            3,
            encode_master_vision_event_report_body(
                master._active_hook_context_id,
                master_module.EVENT_ARRIVED,
                0,
            ),
        )
    )
    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: master._state_machine.state == master_module.STATE_CLEAR_OBJECT
        and assistant._state_machine.state == assistant_module.ASSISTANT_STATE_CLEAR_OBJECT,
    )

    _pump_until(
        clock,
        master,
        assistant,
        master_car,
        assistant_car,
        master_uart6,
        assistant_uart6,
        lambda: master._state_machine.state == master_module.STATE_SEARCH_OBJECT
        and assistant._state_machine.state == assistant_module.ASSISTANT_STATE_FOLLOW,
        max_steps=160,
    )

    assert master._state_machine.state == master_module.STATE_SEARCH_OBJECT
    assert assistant._state_machine.state == assistant_module.ASSISTANT_STATE_FOLLOW


def test_duplicate_reliable_event_does_not_repeat_master_state_jump(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    master_module = import_module_clean("vision.master.forward_runtime", monkeypatch)

    master_uart6 = BufferedUart()
    master_uart8 = BufferedUart()
    master = master_module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=master_uart6,
            uart8=master_uart8,
            now_ms=clock,
        ),
    )
    master_car = cars[0]

    for _ in range(10):
        run_runtime_cycle(master)
        _ack_latest_tcp_if_needed(master_uart6)
        clock.advance(20)
        if master._active_hook_context_id is not None:
            break
    assert master._active_hook_context_id is not None

    frame = encode_frame(
        0x02,
        TOPIC_MASTER_VISION_EVENT_REPORT,
        7,
        encode_master_vision_event_report_body(
            master._active_hook_context_id,
            master_module.EVENT_TARGET_FOUND,
            300,
        ),
    )
    master_uart6.push(frame)
    run_runtime_cycle(master)
    _ack_latest_tcp_if_needed(master_uart6)
    for _ in range(10):
        if master_uart8.messages:
            latest = decode_frame(master_uart8.messages[-1])
            assert latest is not None
            if latest["mode"] == 0x02:
                master_uart8.push(ack_last_frame(master_uart8))
                break
        clock.advance(20)
        run_runtime_cycle(master)
    clock.advance(20)
    master_uart6.push(frame)
    run_runtime_cycle(master)
    _ack_latest_tcp_if_needed(master_uart6)

    orbit_events = [event for event in master_car.events if isinstance(event, tuple) and event[0] == "set_orbit_target"]
    assert master._state_machine.state == master_module.STATE_ORBITING
    assert len(orbit_events) == 1


def test_duplicate_assistant_state_sync_does_not_reapply_local_task(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    assistant_module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    assistant_uart6 = BufferedUart()
    assistant_uart8 = BufferedUart()
    assistant = assistant_module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=assistant_uart6,
            uart8=assistant_uart8,
            now_ms=clock,
        ),
    )

    frame = encode_frame(
        0x02,
        TOPIC_ASSISTANT_STATE_SYNC,
        9,
        encode_assistant_state_sync_body(assistant_module.ASSISTANT_STATE_APPROACH_OBJECT, 1, 1),
    )
    assistant_uart8.push(frame)
    run_runtime_cycle(assistant)
    assert assistant._sync_apply_count == 1
    assert assistant._state_machine.state == assistant_module.ASSISTANT_STATE_APPROACH_OBJECT
    for _ in range(10):
        if assistant_uart6.messages:
            break
        clock.advance(20)
        run_runtime_cycle(assistant)
    first_uart6_messages = list(assistant_uart6.messages)
    assert first_uart6_messages

    assistant_uart8.push(frame)
    clock.advance(20)
    run_runtime_cycle(assistant)

    assert assistant._sync_apply_count == 1
    assert assistant._state_machine.state == assistant_module.ASSISTANT_STATE_APPROACH_OBJECT
    assert assistant_uart6.messages == first_uart6_messages


def test_duplicate_assistant_event_report_does_not_requeue_master_transition(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    master_module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    master_uart6 = BufferedUart()
    master_uart8 = BufferedUart()
    master = master_module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=master_uart6,
            uart8=master_uart8,
            now_ms=clock,
        ),
    )
    master_car = cars[0]

    for _ in range(10):
        run_runtime_cycle(master)
        _ack_latest_tcp_if_needed(master_uart6)
        clock.advance(20)
        if master._active_hook_context_id is not None:
            break
    assert master._active_hook_context_id is not None

    target_found = encode_frame(
        0x02,
        TOPIC_MASTER_VISION_EVENT_REPORT,
        1,
        encode_master_vision_event_report_body(
            master._active_hook_context_id,
            master_module.EVENT_TARGET_FOUND,
            300,
        ),
    )
    master_uart6.push(target_found)
    run_runtime_cycle(master)
    _ack_latest_tcp_if_needed(master_uart6)
    for _ in range(10):
        latest = decode_frame(master_uart8.messages[-1])
        assert latest is not None
        if latest["mode"] == 0x02:
            master_uart8.push(ack_last_frame(master_uart8))
            break
        clock.advance(20)
        run_runtime_cycle(master)
    clock.advance(20)
    run_runtime_cycle(master)
    master_car.command_lock = False
    clock.advance(20)
    run_runtime_cycle(master)
    for _ in range(10):
        latest = decode_frame(master_uart8.messages[-1])
        assert latest is not None
        if latest["mode"] == 0x02:
            master_uart8.push(ack_last_frame(master_uart8))
            break
        clock.advance(20)
        run_runtime_cycle(master)
    clock.advance(20)
    run_runtime_cycle(master)

    report = encode_frame(
        0x02,
        TOPIC_ASSISTANT_EVENT_REPORT,
        11,
        encode_assistant_vision_event_report_body(master_module.EVENT_TARGET_FOUND, 300),
    )
    master_uart8.push(report)
    run_runtime_cycle(master)
    orbit_sync_body = encode_assistant_state_sync_body(3, 1, 0)
    for _ in range(10):
        orbit_sync_count = 0
        for message in master_uart8.messages:
            frame = decode_frame(message)
            assert frame is not None
            if (
                frame["mode"] == 0x02
                and frame["topic"] == TOPIC_ASSISTANT_STATE_SYNC
                and frame["body"][:4] == orbit_sync_body
            ):
                orbit_sync_count += 1
        if orbit_sync_count >= 1:
            break
        clock.advance(20)
        run_runtime_cycle(master)

    master_uart8.push(report)
    clock.advance(20)
    run_runtime_cycle(master)

    orbit_sync_count_after_duplicate = 0
    for message in master_uart8.messages:
        frame = decode_frame(message)
        assert frame is not None
        if (
            frame["mode"] == 0x02
            and frame["topic"] == TOPIC_ASSISTANT_STATE_SYNC
            and frame["body"][:4] == orbit_sync_body
        ):
            orbit_sync_count_after_duplicate += 1

    assert orbit_sync_count == 1
    assert orbit_sync_count_after_duplicate == 1


def test_resent_assistant_state_sync_does_not_reapply_local_task(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    assistant_module = import_module_clean("vision.assistant.follow_runtime", monkeypatch)
    sender_uart8, assistant_uart8 = make_linked_uart_pair()
    assistant_uart6 = BufferedUart()
    sender = create_transport(ROLE_MASTER, uart8=sender_uart8, now_ms=clock)
    assistant = assistant_module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=assistant_uart6,
            uart8=assistant_uart8,
            now_ms=clock,
        ),
    )

    assert sender.tcp(UART8).write(
        TOPIC_ASSISTANT_STATE_SYNC,
        encode_assistant_state_sync_body(assistant_module.ASSISTANT_STATE_APPROACH_OBJECT, 1, 1),
    ) == "accepted"
    sender.poll_tx()
    assistant.poll_transport_rx()
    assistant.step()
    assistant.transport_service._ack_candidate = None
    assistant.poll_transport_tx()
    first_uart6_count = len(assistant_uart6.messages)
    assert assistant._sync_apply_count == 1

    clock.advance(150)
    sender.poll_tx()
    run_runtime_cycle(assistant)

    assert assistant._sync_apply_count == 1
    assert len(assistant_uart6.messages) == first_uart6_count


def test_resent_assistant_event_report_does_not_repeat_master_transition(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    master_module = import_module_clean("vision.master.forward_runtime", monkeypatch)
    master_uart6 = BufferedUart()
    sender_uart8, master_uart8 = make_linked_uart_pair()
    sender = create_transport(ROLE_ASSISTANT, uart8=sender_uart8, now_ms=clock)
    master = master_module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=master_uart6,
            uart8=master_uart8,
            now_ms=clock,
        ),
    )
    master_car = cars[0]

    for _ in range(10):
        run_runtime_cycle(master)
        _ack_latest_tcp_if_needed(master_uart6)
        clock.advance(20)
        if master._active_hook_context_id is not None:
            break
    assert master._active_hook_context_id is not None

    target_found = encode_frame(
        0x02,
        TOPIC_MASTER_VISION_EVENT_REPORT,
        1,
        encode_master_vision_event_report_body(
            master._active_hook_context_id,
            master_module.EVENT_TARGET_FOUND,
            300,
        ),
    )
    master_uart6.push(target_found)
    run_runtime_cycle(master)
    _ack_latest_tcp_if_needed(master_uart6)
    for _ in range(10):
        latest = decode_frame(master_uart8.messages[-1])
        assert latest is not None
        if latest["mode"] == 0x02:
            master_uart8.push(ack_last_frame(master_uart8))
            break
        clock.advance(20)
        run_runtime_cycle(master)
    clock.advance(20)
    run_runtime_cycle(master)
    master_car.command_lock = False
    clock.advance(20)
    run_runtime_cycle(master)
    for _ in range(10):
        latest = decode_frame(master_uart8.messages[-1])
        assert latest is not None
        if latest["mode"] == 0x02:
            master_uart8.push(ack_last_frame(master_uart8))
            break
        clock.advance(20)
        run_runtime_cycle(master)
    clock.advance(20)
    run_runtime_cycle(master)

    assert sender.tcp(UART8).write(
        TOPIC_ASSISTANT_EVENT_REPORT,
        encode_assistant_vision_event_report_body(master_module.EVENT_TARGET_FOUND, 300),
    ) == "accepted"
    sender.poll_tx()
    master.poll_transport_rx()
    master.step()
    master.transport_service._ack_candidate = None
    master.poll_transport_tx()
    orbit_events_first = [
        event for event in master_car.events if isinstance(event, tuple) and event[0] == "set_orbit_target"
    ]

    clock.advance(150)
    sender.poll_tx()
    run_runtime_cycle(master)
    orbit_events_after = [
        event for event in master_car.events if isinstance(event, tuple) and event[0] == "set_orbit_target"
    ]

    assert len(orbit_events_first) == 1
    assert len(orbit_events_after) == 1
