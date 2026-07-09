"""transport runtime 外观测试.

@file tests/unit/runtime/test_transport_runtime_surface.py
"""

from protocol.codec import (
    AS_ARG,
    AS_STATE,
    AS_TARGET,
    AS_TH,
    CTL_ACTION,
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
from play.routines import assistant_return_garage, master_return_garage
from tests.unit.runtime.transport_runtime_support import (
    BufferedUart,
    ManualClock,
    ack_last_frame,
    import_module_clean,
    install_fake_core,
    run_runtime_cycle,
)


def _vel(vx, vy, omega=0.0, has_omega=False):
    return [float(vx), float(vy), float(omega), bool(has_omega)]


def _master_event(context_id, event, value, threshold=(0, 0, 0, 0, 0, 0)):
    return (int(context_id), int(event), int(value), tuple(threshold))


def _assistant_sync(state, target, arg, threshold=(0, 0, 0, 0, 0, 0)):
    return (int(state), int(target), int(arg), tuple(threshold))


MASTER_STATE_STARTUP_MOVE = 9
ASSISTANT_STATE_STARTUP_MOVE = 8
MASTER_LEAD_DISTANCE = master_return_garage.SEQUENCE[1] / 100.0
MASTER_RETURN_POSITION_SPEED = master_return_garage.SEQUENCE[2]
MASTER_RETURN_FORWARD_SPEED = master_return_garage.SEQUENCE[7]
MASTER_FINAL_FORWARD_SPEED = master_return_garage.SEQUENCE[13]
ASSISTANT_LEAD_DISTANCE = assistant_return_garage.SEQUENCE[1] / 100.0
ASSISTANT_RETURN_POSITION_SPEED = assistant_return_garage.SEQUENCE[2]


def _pack_task_arg(config_id, object_id):
    packed = (int(config_id) & 0xFF) | ((int(object_id) & 0xFF) << 8)
    if packed >= 0x8000:
        packed -= 0x10000
    return packed


def _task_pending(module, kind, context_id, state, target, arg, queued=False):
    return (kind, context_id, state, target, arg, queued)


def _sync_pending(module, kind, state, target, arg, threshold, queued=False):
    return (kind, state, target, arg, threshold, queued)


def _local_sync(module, state, target, arg, threshold, queued=False):
    return (state, target, arg, threshold, queued)


def _gate(action, queued=False):
    return (action, queued)


def _complete_master_startup_move(runtime, car) -> None:
    runtime._sm.step(False)
    runtime._sm.poll_assistant_request()
    runtime._sm.mark_startup_sync_acknowledged()
    runtime._p_ast = None
    while runtime._sm.state == MASTER_STATE_STARTUP_MOVE:
        run_runtime_cycle(runtime)
        car.command_lock = False
    runtime.step_role()
    runtime.poll_transport_tx()


def _complete_assistant_startup_move(runtime, car) -> None:
    runtime._sm.apply_master_state(ASSISTANT_STATE_STARTUP_MOVE, 0, 0)
    runtime.step()
    runtime.poll_transport_tx()
    while runtime._sm.state == ASSISTANT_STATE_STARTUP_MOVE:
        runtime.step()
        runtime.poll_transport_tx()
        car.command_lock = False
    runtime.step_role()
    runtime.poll_transport_tx()


def _ack_assistant_startup_follow_sync(runtime, uart6, clock) -> None:
    uart6.push(ack_last_frame(uart6))
    clock.advance(20)
    run_runtime_cycle(runtime)


def test_master_runtime_exposes_external_transport_cycle(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart()
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8, now_ms=clock),
    )

    _complete_master_startup_move(runtime, cars[0])
    keep_running = run_runtime_cycle(runtime)

    assert keep_running is False
    assert hasattr(runtime, "poll_transport_rx")
    assert hasattr(runtime, "poll_transport_tx")
    frame = decode_frame(uart6.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_MASTER_VISION_TASK_SYNC
    assert "transport_step" in cars[0].events


def test_master_runtime_applies_orbit_velocity_after_task_sync_delivery(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    car = cars[0]
    runtime._sm.state = module.STATE_ORBITING
    runtime._last_state = module.STATE_ORBITING
    runtime._p_task = _task_pending(
        module,
        module.RK_T_ORBIT,
        9,
        module.STATE_ORBITING,
        module.TARGET_OBJECT,
        module.MASTER_ORBIT_TASK_CONFIG_ID,
    )
    car.set_orbit_target(module.MASTER_ORBIT_TARGET_DEG, module.MASTER_ORBIT_RADIUS_SCALE)

    runtime._queue_pending_task_sync()
    runtime.poll_transport_tx()
    uart6.push(ack_last_frame(uart6))
    clock.advance(20)
    run_runtime_cycle(runtime)
    uart6.push(
        encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(1.25, -0.5, 0.0, False),
        )
    )
    clock.advance(20)
    run_runtime_cycle(runtime)

    assert ("set_orbit_velocity_correction", 1.25, -0.5) in car.events


def test_master_runtime_skips_orbit_correction_after_chassis_orbit_finished(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    car = cars[0]
    runtime._sm.state = module.STATE_ORBITING
    runtime._last_state = module.STATE_ORBITING
    runtime._orb_act = True
    runtime._u6v = _vel(1.25, -0.5)
    car.command_lock = False
    car.orbit_mode = False

    def set_orbit_velocity_correction(vx, vy):
        raise RuntimeError("orbit velocity correction requires orbit mode")

    car.set_orbit_velocity_correction = set_orbit_velocity_correction

    runtime.step_role()

    assert runtime._err == "none"
    assert runtime._sm.state == module.STATE_SEARCH_OBJECT


def test_master_runtime_writes_zero_velocity_when_orbit_finishes(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    car = cars[0]
    runtime._sm.state = module.STATE_ORBITING
    runtime._last_state = module.STATE_ORBITING
    runtime._orb_act = True
    car.command_lock = False
    car.control_vx = 1.25
    car.control_vy = -0.5
    car.control_omega = 0.0
    car.control_omega_active = True

    runtime._advance_state_machine()

    assert runtime._sm.state != module.STATE_ORBITING
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_runtime_applies_local_velocity_after_task_delivery(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    uart6 = BufferedUart()
    uart8 = BufferedUart()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(ROLE_MASTER, uart6=uart6, uart8=uart8, now_ms=clock),
    )

    _complete_master_startup_move(runtime, cars[0])
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
        "source": None,
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }
    forwarded = decode_frame(uart8.messages[-1])
    assert forwarded is not None
    assert forwarded["topic"] == TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
    assert decode_velocity_body(forwarded["body"][:7]) == (1.0, -2.0, 0.0, False)


def test_master_runtime_holds_push_heading_after_orbit(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_SEARCH_OBJECT
    runtime._sm._orbit_done = True
    runtime._sm._edge = "left"
    runtime._u6v = _vel(0.0, 0.0)

    runtime._apply_latest_uart6_velocity()

    assert ("set_heading_target", 90.0) in cars[0].events


def test_master_runtime_clears_local_velocity_when_vision_event_arrives(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._act_ctx = 7
    runtime._u6v = _vel(1.0, -2.0)
    cars[0].handle_velocity_packet(1.0, -2.0, 0.0, "uart6", False)

    runtime._handle_task_event(_master_event(7, 6, 9))

    assert runtime._u6v is None
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_runtime_keeps_transport_and_feedforward_flow_quiet(
    monkeypatch, capsys
) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )

    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._p_task = _task_pending(
        module,
        module.RK_T_FINISH,
        8,
        module.STATE_TRANSPORT_OBJECT,
        module.TARGET_EDGE_LINE,
        module.MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID,
    )
    runtime._apply_transport_velocity()

    runtime._sm.state = module.STATE_CLEAR_OBJECT
    runtime._p_ast = _sync_pending(
        module,
        module.RK_A_CLEAR,
        5,
        1,
        1,
        (0, 0, 0, 0, 0, 0),
    )
    runtime._queue_feedforward_velocity()

    captured = capsys.readouterr().out
    assert "master_transport:" not in captured
    assert "master_feedforward:" not in captured


def test_master_runtime_transport_ignores_local_vision_x_correction(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._u6v = _vel(1.5, -0.5)

    runtime._apply_transport_velocity()

    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": module.TRANSPORT_FORWARD_SPEED - 0.5,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_holds_before_finish_task_is_delivered(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._ctx = 9
    runtime._p_task = _task_pending(
        module,
        module.RK_T_FINISH,
        9,
        module.STATE_TRANSPORT_OBJECT,
        module.TARGET_EDGE_LINE,
        module.MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID,
    )

    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_runtime_blocks_feedforward_before_finish_task_is_delivered(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._ctx = 9
    runtime._p_task = _task_pending(
        module,
        module.RK_T_FINISH,
        9,
        module.STATE_TRANSPORT_OBJECT,
        module.TARGET_EDGE_LINE,
        module.MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID,
        True,
    )

    runtime._queue_feedforward_velocity()
    runtime.poll_transport_tx()

    assert uart8.messages == []


def test_master_runtime_blocks_transport_feedforward_after_finish_task_ready(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._ctx = 9
    runtime._act_ctx = 9
    cars[0].handle_velocity_packet(0.0, module.TRANSPORT_FORWARD_SPEED, 0.0, None, False)

    runtime._queue_feedforward_velocity()
    runtime.poll_transport_tx()

    assert uart8.messages == []


def test_master_runtime_avoidance_alignment_enters_shift_transport(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_SEARCH_OBJECT
    runtime._sm._ctx = 9
    runtime._act_ctx = 9
    runtime._sm._obj_id = 2
    runtime._sm._av_align = True
    runtime._sm._orbit_done = True
    runtime._sm._orbit_req = True
    runtime._sm._m_aligned = True

    runtime._sm.handle_assistant_aligned(0)
    runtime._drain_state_machine_outputs()

    assert runtime._sm.state == module.STATE_SEARCH_OBJECT
    assert runtime._sm._av_shift is True
    assert runtime._p_ast is not None
    assert runtime._p_ast[0] == module.RK_A_TRANSPORT
    assert runtime._p_task is None


def test_master_runtime_avoidance_shift_starts_formal_orbit_then_aligns(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._edge = "bottom"
    runtime._sm._av_shift = True
    runtime._sm._tr_req = True
    runtime._sm._tr_ready = True

    runtime._sm.handle_assistant_cleared(0)
    runtime._drain_state_machine_outputs()

    assert ("set_orbit_target", 180.0, float(module.MASTER_ORBIT_RADIUS_SCALE)) in cars[0].events
    assert runtime._sm.state == module.STATE_ORBITING
    assert runtime._p_ast is None
    cars[0].command_lock = False
    runtime._advance_state_machine()
    runtime._drain_state_machine_outputs()

    assert runtime._sm.state == module.STATE_SEARCH_OBJECT
    assert runtime._p_ast is not None
    assert runtime._p_ast[0] == module.RK_A_ORBIT
    assert runtime._p_task is not None


def test_master_runtime_closes_finish_context_after_arrived(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._ctx = 9
    runtime._act_ctx = 9

    runtime._handle_task_event(_master_event(9, module.EVENT_ARRIVED, 0))

    assert runtime._sm.state == module.STATE_CLEAR_OBJECT
    assert runtime._act_ctx is None


def test_master_runtime_holds_zero_during_clear_sync(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_CLEAR_OBJECT
    cars[0].handle_velocity_packet(0.0, module.TRANSPORT_FORWARD_SPEED, 0.0, "master_transport", False)

    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_runtime_blocks_feedforward_while_assistant_sync_pending(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._p_ast = _sync_pending(
        module,
        module.RK_A_CLEAR,
        5,
        1,
        1,
        (0, 0, 0, 0, 0, 0),
    )

    runtime._queue_feedforward_velocity()
    runtime.poll_transport_tx()

    assert uart8.messages == []


def test_master_runtime_forwards_target_threshold_to_assistant(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("role.master.state_machine", monkeypatch)
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
    runtime._sm.state = module.STATE_SEARCH_OBJECT
    runtime._act_ctx = int(runtime._sm._ctx)

    runtime._handle_task_event(
        _master_event(int(runtime._sm._ctx), module.EVENT_TARGET_FOUND, 2, threshold)
    )
    runtime._drain_state_machine_outputs()
    runtime._queue_pending_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart8.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_STATE_SYNC
    packet = decode_assistant_state_sync_body(frame["body"][:10])
    assert packet[AS_STATE] == state_module.ASSISTANT_OBJECT_SYNC_STATE
    assert packet[AS_TARGET] == state_module.ASSISTANT_OBJECT_SYNC_TARGET
    assert packet[AS_ARG] == _pack_task_arg(module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID, 2)
    assert packet[AS_TH] == threshold


def test_master_runtime_encodes_latest_threshold_when_sending_assistant_sync(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("role.master.state_machine", monkeypatch)
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
    runtime._obj_th = latest_threshold
    runtime._p_ast = _sync_pending(
        module,
        module.RK_A_OBJ,
        state_module.ASSISTANT_OBJECT_SYNC_STATE,
        state_module.ASSISTANT_OBJECT_SYNC_TARGET,
        _pack_task_arg(module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID, 2),
        old_threshold,
    )

    runtime._queue_pending_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart8.messages[-1])
    assert frame is not None
    assert decode_assistant_state_sync_body(frame["body"][:10])[AS_TH] == latest_threshold


def test_master_runtime_pauses_local_vision_control_from_reliable_packet(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_SEARCH_OBJECT
    runtime._u6v = _vel(1.0, -2.0)
    cars[0].handle_velocity_packet(1.0, -2.0, 0.0, "uart6", False)

    run_runtime_cycle(runtime)

    assert runtime._lv_pause is True
    assert runtime._u6v is None
    assert cars[0].last_chassis_target == {
        "source": None,
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
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._ctx = 9
    runtime._act_ctx = 9

    run_runtime_cycle(runtime)

    assert runtime._lv_pause is False
    assert cars[0].last_chassis_target["source"] is None
    for _ in range(int(module.MOTION_STOP_CONFIRM_TICKS) - 1):
        runtime._apply_motion_outputs()
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": module.TRANSPORT_FORWARD_SPEED,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_resume_discards_cached_velocity_until_next_udp(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_SEARCH_OBJECT
    runtime._lv_pause = True

    run_runtime_cycle(runtime)

    assert runtime._lv_pause is False
    assert runtime._u6v is None
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
        "source": None,
        "vx": 2.0,
        "vy": 3.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_transport_transition_clears_local_vision_pause(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._lv_pause = True
    runtime._u6v = _vel(1.5, -0.5)
    runtime._sm.state = module.STATE_SEARCH_OBJECT
    runtime._last_state = module.STATE_SEARCH_OBJECT

    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._ctx = 9
    runtime._act_ctx = 9

    runtime._run_role_cycle()
    run_runtime_cycle(runtime)

    assert runtime._lv_pause is False
    assert cars[0].last_chassis_target["source"] is None
    for _ in range(int(module.MOTION_STOP_CONFIRM_TICKS) - 1):
        runtime._apply_motion_outputs()
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": module.TRANSPORT_FORWARD_SPEED,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_waits_for_lateral_stop_before_transport_push(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    car = cars[0]
    runtime._sm.state = module.STATE_TRANSPORT_OBJECT
    runtime._sm._ctx = 9
    runtime._act_ctx = 9
    car.w_filt[0] = float(module.MOTION_STOP_SPEED_THRESHOLD) * 2.0

    runtime._apply_motion_outputs()

    assert car.last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }

    car.w_filt[0] = 0.0
    for _ in range(int(module.MOTION_STOP_CONFIRM_TICKS) - 1):
        runtime._apply_motion_outputs()
        assert car.last_chassis_target["source"] is None

    runtime._apply_motion_outputs()

    assert car.last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": module.TRANSPORT_FORWARD_SPEED,
        "omega": 0.0,
        "has_omega": False,
    }

    car.w_filt[0] = float(module.MOTION_STOP_SPEED_THRESHOLD) * 2.0
    runtime._apply_motion_outputs()

    assert car.last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": module.TRANSPORT_FORWARD_SPEED,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_clears_local_velocity_when_assistant_event_arrives(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._u6v = _vel(1.0, -2.0)
    cars[0].handle_velocity_packet(1.0, -2.0, 0.0, "uart6", False)

    run_runtime_cycle(runtime)

    assert runtime._u6v is None
    assert ("handle_velocity", None, 0.0, 0.0, 0.0) in cars[0].events


def test_master_runtime_keeps_locked_pose_when_assistant_event_arrives(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._u6v = _vel(1.0, -2.0)
    runtime._sm.state = module.STATE_SEARCH_OBJECT
    runtime._last_state = module.STATE_SEARCH_OBJECT
    cars[0].command_lock = True
    cars[0].control_vx = 0.0
    cars[0].control_vy = 0.0
    cars[0].control_omega = 0.0
    cars[0].control_omega_active = True
    cars[0].control_x = 1.0
    cars[0].control_y = 2.0
    cars[0].control_angle = 90.0
    cars[0].control_x_active = True
    cars[0].control_y_active = True
    cars[0].control_angle_active = True

    run_runtime_cycle(runtime)

    assert runtime._u6v is None
    assert cars[0].command_lock is True
    assert cars[0].control_state["x"] == 1.0
    assert cars[0].control_state["y"] == 2.0
    assert ("handle_velocity", "assistant_event", 0.0, 0.0, 0.0) not in cars[0].events


def test_assistant_runtime_fuses_uart6_and_uart8_velocity(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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

    _complete_assistant_startup_move(runtime, cars[0])
    runtime.poll_transport_tx()
    uart6.push(ack_last_frame(uart6))
    clock.advance(20)
    run_runtime_cycle(runtime)
    assert cars[0].control_state == {"vx": 1.5, "vy": -0.25, "omega": 0.25}


def test_assistant_runtime_ignores_velocity_received_during_startup_move(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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

    runtime._sm.apply_master_state(module.ASSISTANT_STATE_STARTUP_MOVE, 0, 0)
    runtime.poll_transport_rx()
    for _ in range(8):
        runtime.step()
        runtime.poll_transport_tx()
        cars[0].command_lock = False
        if runtime._sm.state != module.ASSISTANT_STATE_STARTUP_MOVE:
            break

    assert runtime._sm.state == module.ASSISTANT_STATE_FOLLOW
    assert runtime._u6v is None
    assert runtime._u8v is None
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_announces_follow_to_local_vision_on_startup(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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

    assert uart6.messages == []

    _complete_assistant_startup_move(runtime, runtime._car)
    runtime._queue_pending_local_vision_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart6.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_VISION_TASK_SYNC
    packet = decode_assistant_vision_task_sync_body(frame["body"][:10])
    assert packet[AS_STATE] == module.ASSISTANT_STATE_FOLLOW
    assert packet[AS_TARGET] == 0
    assert packet[AS_ARG] == 0
    assert packet[AS_TH] == (0, 0, 0, 0, 0, 0)


def test_assistant_runtime_applies_orbit_velocity_after_local_sync_delivery(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    car = cars[0]
    runtime._sm.state = module.ASSISTANT_STATE_ORBIT
    runtime._p_local = _local_sync(
        module,
        module.ASSISTANT_STATE_ORBIT,
        module.ASSISTANT_TARGET_OBJECT,
        _pack_task_arg(module._ASSISTANT_ORBIT_OBJECT_CONFIG_ID, 1),
        (0, 0, 0, 0, 0, 0),
    )
    car.set_orbit_target(module._ASSISTANT_ORBIT_TARGET_DEG, module._ASSISTANT_ORBIT_RADIUS_SCALE)

    runtime._queue_pending_local_vision_sync()
    runtime.poll_transport_tx()
    uart6.push(ack_last_frame(uart6))
    clock.advance(20)
    run_runtime_cycle(runtime)
    uart6.push(
        encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(-0.75, 0.25, 0.0, False),
        )
    )
    clock.advance(20)
    run_runtime_cycle(runtime)

    assert ("set_orbit_velocity_correction", -0.75, 0.25) in car.events


def test_assistant_runtime_ignores_local_pause_during_orbit(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart(
        incoming=(
            encode_frame(
                0x02,
                TOPIC_LOCAL_VISION_CONTROL,
                9,
                encode_local_vision_control_body(LOCAL_VISION_CONTROL_PAUSE),
            )
            + encode_frame(
                0x01,
                TOPIC_LOCAL_VISION_VELOCITY,
                0,
                encode_velocity_body(-0.75, 0.25, 0.0, False),
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
    car = cars[0]
    runtime._sm.state = module.ASSISTANT_STATE_ORBIT
    runtime._sm.arg = _pack_task_arg(module._ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID, 1)
    car.set_orbit_target(module._ASSISTANT_ORBIT_TARGET_DEG, module._ASSISTANT_ORBIT_RADIUS_SCALE)

    original_handle_velocity = car.handle_velocity_packet

    def handle_velocity_packet(vx, vy, omega, source, has_omega=True):
        car.orbit_mode = False
        original_handle_velocity(vx, vy, omega, source, has_omega)

    def set_orbit_velocity_correction(vx, vy):
        if not car.orbit_mode:
            raise RuntimeError("orbit velocity correction requires orbit mode")
        car.events.append(("set_orbit_velocity_correction", float(vx), float(vy)))

    car.handle_velocity_packet = handle_velocity_packet
    car.set_orbit_velocity_correction = set_orbit_velocity_correction

    run_runtime_cycle(runtime)

    assert runtime._err == "none"
    assert car.orbit_mode is True
    assert ("handle_velocity", "local_vision_pause", 0.0, 0.0, 0.0) not in car.events


def test_assistant_runtime_skips_orbit_correction_after_chassis_orbit_finished(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    car = cars[0]
    runtime._sm.state = module.ASSISTANT_STATE_ORBIT
    runtime._last_approach_arg = _pack_task_arg(module._ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID, 1)
    runtime._obj_id = 1
    runtime._u6v = _vel(-0.75, 0.25)
    car.command_lock = False
    car.orbit_mode = False

    def set_orbit_velocity_correction(vx, vy):
        raise RuntimeError("orbit velocity correction requires orbit mode")

    car.set_orbit_velocity_correction = set_orbit_velocity_correction

    runtime.step_motion_input()

    assert runtime._err == "none"
    assert runtime._sm.state == module.ASSISTANT_STATE_APPROACH_OBJECT


def test_assistant_runtime_avoidance_orbit_enters_realign(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart()
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_ASSISTANT_STATE_SYNC,
            7,
            encode_assistant_state_sync_body(
                module.ASSISTANT_STATE_ORBIT,
                module.ASSISTANT_TARGET_OBJECT,
                _pack_task_arg(0, 2),
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
    car = cars[0]

    run_runtime_cycle(runtime)

    assert (
        "set_orbit_target",
        90.0,
        float(module._ASSISTANT_ORBIT_RADIUS_SCALE),
    ) in car.events

    car.command_lock = False
    car.orbit_mode = False
    clock.advance(20)
    runtime.step_motion_input()

    assert runtime._sm.state == module.ASSISTANT_STATE_APPROACH_OBJECT
    assert runtime._realign is True

    runtime._queue_pending_local_vision_sync()
    runtime.poll_transport_tx()
    uart6.push(ack_last_frame(uart6))
    clock.advance(20)
    run_runtime_cycle(runtime)
    uart6.push(
        encode_frame(
            0x01,
            TOPIC_LOCAL_VISION_VELOCITY,
            0,
            encode_velocity_body(0.5, -0.25, 0.0, False),
        )
    )
    clock.advance(20)
    run_runtime_cycle(runtime)

    assert ("set_heading_target", 90.0) in car.events


def test_assistant_runtime_formal_orbit_uses_formal_heading_after_avoidance(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    uart8 = BufferedUart(
        incoming=encode_frame(
            0x02,
            TOPIC_ASSISTANT_STATE_SYNC,
            7,
            encode_assistant_state_sync_body(
                module.ASSISTANT_STATE_ORBIT,
                module.ASSISTANT_TARGET_OBJECT,
                _pack_task_arg(module._ASSISTANT_ORBIT_OBJECT_CONFIG_ID, 2),
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

    assert (
        "set_orbit_target",
        float(module._ASSISTANT_ORBIT_TARGET_DEG),
        float(module._ASSISTANT_ORBIT_RADIUS_SCALE),
    ) in cars[0].events
    assert runtime._av_orbit is False


def test_assistant_runtime_forwards_master_threshold_to_local_vision(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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

    _complete_assistant_startup_move(runtime, cars[0])
    _ack_assistant_startup_follow_sync(runtime, uart6, clock)
    run_runtime_cycle(runtime)
    runtime._queue_pending_local_vision_sync()
    runtime.poll_transport_tx()

    frame = decode_frame(uart6.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_VISION_TASK_SYNC
    packet = decode_assistant_vision_task_sync_body(frame["body"][:10])
    assert packet[AS_STATE] == module.ASSISTANT_STATE_APPROACH_OBJECT
    assert packet[AS_TARGET] == module.ASSISTANT_TARGET_OBJECT
    assert packet[AS_ARG] == _pack_task_arg(1, 2)
    assert packet[AS_TH] == threshold


def test_assistant_runtime_treats_master_sync_as_zero_velocity(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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

    _complete_assistant_startup_move(runtime, cars[0])
    run_runtime_cycle(runtime)

    assert runtime._u6v is None
    assert runtime._u8v is None
    assert runtime._p_local == _local_sync(
        module,
        module.ASSISTANT_STATE_APPROACH_OBJECT,
        module.ASSISTANT_TARGET_OBJECT,
        _pack_task_arg(1, 2),
        (0, 0, 0, 0, 0, 0),
    )
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_pauses_chassis_from_local_vision_control(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    runtime._u6v = _vel(1.0, 2.0)
    runtime._u8v = _vel(3.0, 4.0)
    cars[0].handle_velocity_packet(4.0, 6.0, 0.0, "assistant", False)

    _complete_assistant_startup_move(runtime, cars[0])
    _ack_assistant_startup_follow_sync(runtime, uart6, clock)
    uart6.push(
        encode_frame(
            0x02,
            TOPIC_LOCAL_VISION_CONTROL,
            9,
            encode_local_vision_control_body(LOCAL_VISION_CONTROL_PAUSE),
        )
    )
    run_runtime_cycle(runtime)

    assert runtime._lv_pause is True
    assert runtime._u6v is None
    assert runtime._u8v is None
    assert cars[0].last_chassis_target == {
        "source": None,
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
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    runtime._sm.state = module.ASSISTANT_STATE_TRANSPORT_OBJECT
    runtime._u8v = _vel(0.0, 4.0)

    run_runtime_cycle(runtime)

    assert runtime._lv_pause is False
    feedforward_scale = module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE
    expected_vy = -float(module.motion_params.TRANSPORT_FORWARD_SPEED) * feedforward_scale
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": expected_vy,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_runtime_ignores_pause_during_return_follow_play(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    runtime._sm.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._p_local = None

    run_runtime_cycle(runtime)

    assert runtime._lv_pause is False
    assert runtime.play_kind != 0
    assert (
        "set_relative_translation_target",
        0.0,
        ASSISTANT_LEAD_DISTANCE,
        float(ASSISTANT_RETURN_POSITION_SPEED),
    ) in cars[0].events


def test_assistant_runtime_resume_discards_cached_velocity_until_next_udp(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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

    _complete_assistant_startup_move(runtime, cars[0])
    _ack_assistant_startup_follow_sync(runtime, uart6, clock)
    runtime._lv_pause = True
    runtime._p_local = None
    uart6.push(
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
    run_runtime_cycle(runtime)

    assert runtime._lv_pause is False
    assert runtime._u6v is None
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
        "source": None,
        "vx": 2.0,
        "vy": 3.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_runtime_new_sync_clears_local_vision_pause(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._lv_pause = True

    accepted = runtime._apply_sync_context(
        _assistant_sync(
            module.ASSISTANT_STATE_TRANSPORT_OBJECT,
            module.ASSISTANT_TARGET_OBJECT,
            _pack_task_arg(2, 1),
        )
    )

    assert accepted is True
    assert runtime._lv_pause is False


def test_runtime_cycle_requests_each_port_once_for_normal_input(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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


def test_master_runtime_logs_role_cycle_failure_to_board_log(capsys, monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    assert "master_error: traceback start" not in output
    assert "master_error: traceback end" not in output
    assert cars[0].last_exception_text == "master role cycle failed: boom"


def test_master_runtime_reports_role_cycle_failure_via_full_trace_helper(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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

    runtime._sm.step = _positional_step

    keep_running = run_runtime_cycle(runtime)

    assert keep_running is False
    assert calls == [False]


def test_master_runtime_calls_handle_event_without_keyword_args(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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

    runtime._sm.handle_event = _positional_handle_event
    runtime._act_ctx = 7

    runtime._handle_task_event(_master_event(7, 6, 9))

    assert calls == [(7, 6, 9)]


def test_master_runtime_calls_transport_velocity_api_without_keyword_args(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._u6v = _vel(1.0, -2.0)

    runtime._apply_latest_uart6_velocity()

    assert calls == [(1.0, -2.0, 0.0, None, False)]


def test_master_runtime_return_retreat_starts_play_with_lead_translation(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_RETURN_GARAGE_RETREAT

    runtime._apply_motion_outputs()

    assert runtime.play_kind != 0
    assert (
        "set_relative_translation_target",
        0.0,
        MASTER_LEAD_DISTANCE,
        float(MASTER_RETURN_POSITION_SPEED),
    ) in cars[0].events


def test_master_runtime_startup_play_uses_light_sequence(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_STARTUP_MOVE

    runtime._apply_motion_outputs()

    assert runtime.play_kind != 0
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    assert ("set_heading_transition_target", 90.0) in cars[0].events
    cars[0].command_lock = False
    cars[0].heading_est = 90.0
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    assert ("set_heading_transition_target", 0.0) in cars[0].events


def test_master_runtime_final_clear_retreat_enters_return_and_queues_assistant_sync(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("role.master.state_machine", monkeypatch)
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
    runtime._sm.state = module.STATE_CLEAR_OBJECT
    runtime._sm._clr_phase = module.CLEAR_PHASE_RETREAT
    runtime._sm._obj_need = 1
    runtime._sm._m_clear = True
    runtime._sm.handle_assistant_cleared(value=module.CLEAR_PHASE_RETREAT)

    runtime._drain_state_machine_outputs()
    runtime._queue_pending_sync()
    runtime._queue_pending_task_sync()
    runtime.poll_transport_tx()
    runtime.poll_transport_tx()

    assert runtime._sm.state == module.STATE_RETURN_GARAGE_RETREAT
    frame = decode_frame(uart8.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_STATE_SYNC
    assert frame["body"][:10] == encode_assistant_state_sync_body(
        state_module.ASSISTANT_RETURN_FOLLOW_SYNC_STATE,
        state_module.ASSISTANT_RETURN_FOLLOW_SYNC_TARGET,
        0,
    )


def test_master_runtime_starts_return_play_after_assistant_return_sync(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_CLEAR_OBJECT
    runtime._sm._clr_phase = module.CLEAR_PHASE_RETREAT
    runtime._sm._obj_need = 1
    runtime._sm._m_clear = True
    runtime._sm.handle_assistant_cleared(value=module.CLEAR_PHASE_RETREAT)
    runtime._drain_state_machine_outputs()
    runtime._queue_pending_sync()
    runtime._queue_pending_task_sync()
    runtime.poll_transport_tx()
    runtime.poll_transport_tx()

    runtime._run_motion_input_cycle()

    assert runtime._sm.state == module.STATE_RETURN_GARAGE_RETREAT
    assert runtime.play_kind != 0
    assert (
        "set_relative_translation_target",
        0.0,
        MASTER_LEAD_DISTANCE,
        float(MASTER_RETURN_POSITION_SPEED),
    ) in cars[0].events
    frame = decode_frame(uart8.messages[-1])
    assert frame is not None
    assert frame["topic"] == TOPIC_ASSISTANT_STATE_SYNC


def test_master_runtime_turn_back_completes_immediately_after_lock_release(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("role.master.state_machine", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_CLEAR_OBJECT
    runtime._sm._clr_phase = state_module._CLEAR_STAGE_TURN_BACK
    runtime._sm._obj_need = 1
    runtime._tb_rot = True
    cars[0].command_lock = False
    for idx in range(3):
        cars[0].w_filt[idx] = (
            float(module.MOTION_STOP_SPEED_THRESHOLD) + 1.0
        )

    runtime._run_turn_back_phase()
    runtime._drain_state_machine_outputs()

    assert runtime._tb_rot is False
    assert runtime._sm.state == module.STATE_RETURN_GARAGE_RETREAT


def test_master_runtime_turn_back_completes_inside_turn_back_tolerance(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("role.master.state_machine", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_CLEAR_OBJECT
    runtime._sm._clr_phase = state_module._CLEAR_STAGE_TURN_BACK
    runtime._sm._obj_need = 1
    runtime._tb_rot = True
    target_heading_deg = 180.0
    tolerance_deg = float(module.MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG)
    runtime._tb_heading = target_heading_deg
    cars[0].heading_est = target_heading_deg - tolerance_deg + 0.1
    cars[0].command_lock = True

    runtime._run_turn_back_phase()
    runtime._drain_state_machine_outputs()

    assert runtime._tb_rot is False
    assert runtime._sm.state == module.STATE_RETURN_GARAGE_RETREAT
    assert (
        "handle_velocity",
        None,
        0.0,
        0.0,
        0.0,
    ) in cars[0].events


def test_master_runtime_turn_back_keeps_waiting_outside_turn_back_tolerance(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    state_module = import_module_clean("role.master.state_machine", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_CLEAR_OBJECT
    runtime._sm._clr_phase = state_module._CLEAR_STAGE_TURN_BACK
    runtime._sm._obj_need = 1
    runtime._tb_rot = True
    target_heading_deg = 180.0
    tolerance_deg = float(module.MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG)
    runtime._tb_heading = target_heading_deg
    cars[0].heading_est = target_heading_deg - tolerance_deg - 0.1
    cars[0].command_lock = True

    runtime._run_turn_back_phase()
    runtime._drain_state_machine_outputs()

    assert runtime._tb_rot is True
    assert runtime._sm.state == module.STATE_CLEAR_OBJECT


def test_master_runtime_return_play_reaches_hold_velocity_after_yellow_ready(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_RETURN_GARAGE_LINE
    runtime._sm.state = module.STATE_RETURN_GARAGE_RETREAT
    runtime._apply_motion_outputs()
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    assert ("set_heading_transition_target", -90.0) in cars[0].events
    cars[0].heading_est = -90.0
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": float(MASTER_RETURN_FORWARD_SPEED),
        "omega": 0.0,
        "has_omega": False,
    }
    runtime._line_ok = True
    runtime._apply_motion_outputs()
    cars[0].heading_est = -90.0
    runtime._apply_motion_outputs()
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()

    assert ("set_heading_transition_target", 180.0) in cars[0].events
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": float(MASTER_FINAL_FORWARD_SPEED),
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_clears_stale_yellow_ready_when_entering_forward_step(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.STATE_RETURN_GARAGE_RETREAT
    runtime._line_ok = True

    runtime._apply_motion_outputs()
    cars[0].command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    cars[0].heading_est = 90.0
    cars[0].command_lock = False

    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()

    assert runtime._line_ok is False
    assert runtime.play_kind != 0
    assert runtime.play_step == 2
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": float(MASTER_RETURN_FORWARD_SPEED),
        "omega": 0.0,
        "has_omega": False,
    }

    runtime._line_ok = True
    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": float(MASTER_RETURN_FORWARD_SPEED),
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_runtime_step_two_queues_return_line_gate_on_and_off(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    runtime._sm.state = module.STATE_RETURN_GARAGE_RETREAT

    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()
    runtime._car.command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()
    runtime._car.heading_est = 90.0
    runtime._car.command_lock = False
    runtime._apply_motion_outputs()
    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()

    gate_on_frame = decode_frame(uart6.messages[-1])
    assert gate_on_frame is not None
    assert gate_on_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL
    assert (
        decode_local_vision_control_body(gate_on_frame["body"])[CTL_ACTION]
        == LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON
    )
    uart6.push(ack_last_frame(uart6))
    runtime.poll_transport_rx()
    runtime._check_transport_deliveries()

    runtime._line_ok = True
    runtime._apply_motion_outputs()
    runtime._queue_transport_outputs()
    runtime.poll_transport_tx()

    gate_off_frame = decode_frame(uart6.messages[-1])
    assert gate_off_frame is not None
    assert gate_off_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL
    assert (
        decode_local_vision_control_body(gate_off_frame["body"])[CTL_ACTION]
        == LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF
    )


def test_master_runtime_does_not_expose_return_marker_motion_state(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
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
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_MASTER,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )

    runtime._sm.state = module.STATE_FINISHED
    runtime._u6v = _vel(2.0, 2.0)

    runtime._apply_motion_outputs()

    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_reports_role_cycle_failure_via_full_trace_helper(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._p_local = None

    runtime._write_effective_velocity()

    assert runtime.play_kind != 0
    assert (
        "set_relative_translation_target",
        0.0,
        ASSISTANT_LEAD_DISTANCE,
        float(ASSISTANT_RETURN_POSITION_SPEED),
    ) in cars[0].events
    cars[0].command_lock = False
    cars[0].heading_est = 0.0
    runtime._write_effective_velocity()
    runtime._write_effective_velocity()
    assert ("set_heading_transition_target", -90.0) in cars[0].events
    cars[0].command_lock = False
    cars[0].heading_est = -90.0
    runtime._write_effective_velocity()
    runtime._line_ok = True
    runtime._write_effective_velocity()
    cars[0].command_lock = False
    runtime._write_effective_velocity()
    runtime._write_effective_velocity()
    assert ("set_heading_transition_target", 180.0) in cars[0].events


def test_assistant_runtime_step_two_queues_return_line_gate_on(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    runtime._sm.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._p_local = None

    runtime._write_effective_velocity()
    runtime._queue_return_line_gate_action()
    runtime.poll_transport_tx()
    runtime._car.command_lock = False
    runtime._write_effective_velocity()
    runtime._write_effective_velocity()
    runtime._car.heading_est = -90.0
    runtime._car.command_lock = False
    runtime._write_effective_velocity()
    runtime._write_effective_velocity()
    runtime._queue_return_line_gate_action()
    runtime.poll_transport_tx()

    gate_on_frame = decode_frame(uart6.messages[-1])
    assert gate_on_frame is not None
    assert gate_on_frame["topic"] == TOPIC_LOCAL_VISION_CONTROL
    assert (
        decode_local_vision_control_body(gate_on_frame["body"])[CTL_ACTION]
        == LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON
    )


def test_assistant_runtime_keeps_gate_flow_quiet(monkeypatch, capsys) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._gate = _gate(
        LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON
    )

    runtime._queue_return_line_gate_action()

    captured = capsys.readouterr().out
    assert "assistant_gate:" not in captured


def test_assistant_transport_uses_fixed_base_speed_with_local_vision_x(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.ASSISTANT_STATE_TRANSPORT_OBJECT
    runtime._p_local = None
    runtime._u6v = _vel(1.0, 2.0)
    runtime._u8v = _vel(3.0, 4.0)

    runtime._write_effective_velocity()

    feedforward_scale = module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE
    expected_vy = -float(module.motion_params.TRANSPORT_FORWARD_SPEED) * feedforward_scale
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 1.0,
        "vy": expected_vy,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_transport_uses_fixed_base_speed_without_uart8_feedforward(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._sm.state = module.ASSISTANT_STATE_TRANSPORT_OBJECT
    runtime._p_local = None
    runtime._u6v = _vel(1.0, 2.0)
    runtime._u8v = None

    runtime._write_effective_velocity()

    feedforward_scale = module._ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 1.0,
        "vy": -float(module.motion_params.TRANSPORT_FORWARD_SPEED) * feedforward_scale,
        "omega": 0.0,
        "has_omega": False,
    }


def test_assistant_avoidance_shift_reports_when_odometry_distance_reaches_target(
    monkeypatch,
) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._av_shift = True
    runtime._apply_sync_context(
        _assistant_sync(
            module.ASSISTANT_STATE_TRANSPORT_OBJECT,
            module.ASSISTANT_TARGET_OBJECT,
            _pack_task_arg(module._ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID, 2),
        )
    )
    cars[0].odometry.y = -float(module._TRANSPORT_AVOIDANCE_SHIFT_DISTANCE_M)

    runtime.step_motion_input()

    assert runtime._p_report == (module._CLEARED_EVENT, 0, False)
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_transport_syncs_local_transport_object_task(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
        _assistant_sync(
            module.ASSISTANT_STATE_TRANSPORT_OBJECT,
            module.ASSISTANT_TARGET_OBJECT,
            _pack_task_arg(2, 1),
        )
    )

    assert accepted is True
    assert runtime._p_local == _local_sync(
        module,
        module.ASSISTANT_STATE_TRANSPORT_OBJECT,
        module.ASSISTANT_TARGET_OBJECT,
        _pack_task_arg(module._ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID, 1),
        (0, 0, 0, 0, 0, 0),
    )


def test_assistant_runtime_calibrates_pose_when_entering_clear_state(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._apply_sync_context(
        _assistant_sync(
            module.ASSISTANT_STATE_TRANSPORT_OBJECT,
            module.ASSISTANT_TARGET_OBJECT,
            _pack_task_arg(2, 1),
        )
    )

    accepted = runtime._apply_sync_context(
        _assistant_sync(
            module.ASSISTANT_STATE_CLEAR_OBJECT,
            module.ASSISTANT_TARGET_OBJECT,
            module.CLEAR_PHASE_RETREAT,
        )
    )

    assert accepted is True
    assert ("calibrate_pose_to_field_edge", "bottom") in cars[0].events


def test_assistant_runtime_return_follow_syncs_local_yellow_line_task(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
        _assistant_sync(module.ASSISTANT_STATE_RETURN_FOLLOW, 0, 0)
    )

    assert accepted is True
    assert runtime._p_local == _local_sync(
        module,
        module.ASSISTANT_STATE_RETURN_FOLLOW,
        0,
        module.ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID,
        (0, 0, 0, 0, 0, 0),
    )
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_assistant_runtime_return_follow_sync_uses_standard_logs(capsys, monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    uart6 = BufferedUart()
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
            uart6=uart6,
            uart8=uart8,
            now_ms=clock,
        ),
    )

    _complete_assistant_startup_move(runtime, cars[0])
    _ack_assistant_startup_follow_sync(runtime, uart6, clock)
    run_runtime_cycle(runtime)

    output = capsys.readouterr().out
    assert "assistant_state: RETURN_FOLLOW\n" in output
    assert "assistant_return:" not in output


def test_assistant_runtime_return_follow_event_only_marks_alignment(monkeypatch) -> None:
    clock = ManualClock(0)
    install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
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
    runtime._sm.state = module.ASSISTANT_STATE_RETURN_FOLLOW
    runtime._p_local = None
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

    assert runtime._sm.state == module.ASSISTANT_STATE_RETURN_FOLLOW
    assert runtime._line_ok is True


def test_assistant_runtime_finished_sync_clears_inputs_and_stops(monkeypatch) -> None:
    clock = ManualClock(0)
    cars = install_fake_core(monkeypatch)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=create_transport(
            ROLE_ASSISTANT,
            uart6=BufferedUart(),
            uart8=BufferedUart(),
            now_ms=clock,
        ),
    )
    runtime._u6v = _vel(1.0, 2.0)
    runtime._u8v = _vel(3.0, 4.0)

    accepted = runtime._apply_sync_context(
        _assistant_sync(module.ASSISTANT_STATE_FINISHED, 0, 0)
    )

    assert accepted is True
    assert runtime._u6v is None
    assert runtime._u8v is None
    assert cars[0].last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }
