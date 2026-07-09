"""主车状态机纯逻辑测试."""

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))


def _pack_task_arg(config_id, object_id):
    packed = (int(config_id) & 0xFF) | ((int(object_id) & 0xFF) << 8)
    if packed >= 0x8000:
        packed -= 0x10000
    return packed


def _load_master_state_machine():
    module_path = SRC / "role" / "master" / "state_machine.py"
    spec = importlib.util.spec_from_file_location("test_master_state_machine_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load master state machine module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
    return module


def _kind_name(module, kind):
    names = {
        module.RK_A_START: "assistant_startup",
        module.RK_A_OBJ: "assistant_object",
        module.RK_A_ORBIT: "assistant_orbit",
        module.RK_A_FOLLOW: "assistant_follow",
        module.RK_A_TRANSPORT: "assistant_transport",
        module.RK_A_CLEAR: "assistant_clear",
        module.RK_A_RETURN: "assistant_return_line",
        module.RK_A_FINISHED: "assistant_finished",
        module.RK_T_FINISH: "finish_task",
        module.RK_T_RETURN: "return_line_task",
    }
    return names[int(kind)]


def _task_request(module, request):
    result = {
        "context_id": request[module.RQ_CONTEXT],
        "state": request[module.RQ_STATE],
        "target": request[module.RQ_TARGET],
        "arg": request[module.RQ_ARG],
    }
    if request[module.RQ_KIND] != module.RK_NONE:
        result["kind"] = _kind_name(module, request[module.RQ_KIND])
    return result


def _assistant_request(module, request):
    return {
        "kind": _kind_name(module, request[module.RQ_KIND]),
        "state": request[module.RQ_STATE],
        "target": request[module.RQ_TARGET],
        "arg": request[module.RQ_ARG],
    }


def _enter_initial_search(machine):
    machine.step(orbit_finished=False)
    machine.poll_assistant_request()
    machine.mark_startup_sync_acknowledged()
    machine.mark_startup_move_completed()


def _drive_machine_to_post_assistant_orbit_request(module):
    machine = module.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=module.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)
    machine.poll_task_request()
    machine.handle_assistant_target_found(value=300)
    machine.poll_assistant_request()
    return machine


def test_master_state_machine_enters_search_and_builds_task_context() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    _enter_initial_search(machine)
    task_request = machine.poll_task_request()

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _task_request(MasterStateMachine, task_request) == {
        "context_id": 1,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 1,
    }


def test_master_state_machine_waits_for_startup_sync_before_startup_move() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    machine.step(orbit_finished=False)

    assert machine.state == MasterStateMachine.STATE_STARTUP_SYNC
    assert machine.poll_task_request() is None
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_startup",
        "state": MasterStateMachine.ASSISTANT_STARTUP_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_STARTUP_SYNC_TARGET,
        "arg": 0,
    }

    machine.mark_startup_sync_acknowledged()
    assert machine.state == MasterStateMachine.STATE_STARTUP_MOVE
    machine.mark_startup_move_completed()
    task_request = machine.poll_task_request()

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _task_request(MasterStateMachine, task_request) == {
        "context_id": 1,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 1,
    }


def test_master_state_machine_prints_when_entering_new_state(capsys) -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    _enter_initial_search(machine)

    assert capsys.readouterr().out.endswith("master_state: SEARCH_OBJECT\n")


def test_master_state_machine_matching_target_found_enters_orbiting() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    assistant_request = machine.poll_assistant_request()
    orbit_command = machine.poll_orbit_command()

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, assistant_request) == {
        "kind": "assistant_object",
        "state": 2,
        "target": 1,
        "arg": _pack_task_arg(1, 2),
    }
    assert orbit_command is None


def test_master_state_machine_marks_assistant_object_request_kind_before_orbit() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )

    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_object",
        "state": 2,
        "target": 1,
        "arg": _pack_task_arg(1, 2),
    }


def test_master_state_machine_marks_assistant_orbit_request_kind() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)

    machine.handle_assistant_target_found(value=300)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_orbit",
        "state": 3,
        "target": 1,
        "arg": _pack_task_arg(0, 2),
    }

def test_master_state_machine_enters_orbiting_after_assistant_object_ack() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()

    machine.mark_assistant_object_acknowledged()
    orbit_command = machine.poll_orbit_command()

    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert orbit_command == 180.0


def test_master_state_machine_avoidance_demo_uses_perpendicular_master_orbit() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        avoidance_enabled=True,
        avoidance_orbit_offset_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()

    machine.mark_assistant_object_acknowledged()

    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert machine.poll_orbit_command() == -90.0


def test_master_state_machine_avoidance_demo_queues_assistant_orbit_after_master_orbit() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        avoidance_enabled=True,
        avoidance_orbit_offset_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.handle_assistant_target_found(value=300)

    machine.step(orbit_finished=True)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _task_request(MasterStateMachine, machine.poll_task_request()) == {
        "context_id": 3,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 2,
    }
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_orbit",
        "state": MasterStateMachine.ASSISTANT_ORBIT_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_ORBIT_SYNC_TARGET,
        "arg": _pack_task_arg(0, 2),
    }


def test_master_state_machine_avoidance_demo_accepts_late_assistant_target_found() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        avoidance_enabled=True,
        avoidance_orbit_offset_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)

    machine.handle_assistant_target_found(value=300)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_orbit",
        "state": MasterStateMachine.ASSISTANT_ORBIT_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_ORBIT_SYNC_TARGET,
        "arg": _pack_task_arg(0, 2),
    }


def test_master_state_machine_avoidance_demo_hands_off_to_formal_transport() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        avoidance_enabled=True,
        avoidance_orbit_offset_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.handle_assistant_target_found(value=300)
    machine.step(orbit_finished=True)
    machine.poll_task_request()
    machine.poll_assistant_request()

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_transport",
        "state": MasterStateMachine.ASSISTANT_TRANSPORT_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_TRANSPORT_SYNC_TARGET,
        "arg": _pack_task_arg(1, 2),
    }
    machine.mark_transport_ready()
    assert machine.state == MasterStateMachine.STATE_TRANSPORT_OBJECT

    machine.handle_assistant_cleared(value=0)

    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert machine.poll_orbit_command() == 180.0
    machine.step(orbit_finished=True)
    task = _task_request(MasterStateMachine, machine.poll_task_request())
    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_orbit",
        "state": MasterStateMachine.ASSISTANT_ORBIT_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_ORBIT_SYNC_TARGET,
        "arg": _pack_task_arg(1, 2),
    }
    machine.handle_event(
        context_id=task["context_id"],
        event=MasterStateMachine.EVENT_ALIGNED,
        value=0,
    )
    machine.handle_assistant_aligned(value=0)

    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request())["kind"] == "assistant_transport"
    machine.mark_transport_ready()
    assert machine.state == MasterStateMachine.STATE_TRANSPORT_OBJECT


def test_master_state_machine_ignores_mismatched_context_event() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)

    machine.handle_event(
        context_id=9, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() is None
    assert machine.poll_orbit_command() is None


def test_master_state_machine_does_not_repeat_orbit_enter_action() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    first_assistant_request = machine.poll_assistant_request()
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )

    assert _assistant_request(MasterStateMachine, first_assistant_request) == {
        "kind": "assistant_object",
        "state": 2,
        "target": 1,
        "arg": _pack_task_arg(1, 2),
    }
    assert machine.poll_assistant_request() is None
    assert machine.poll_orbit_command() is None


def test_master_state_machine_returns_to_search_when_orbit_finishes() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()

    machine.step(orbit_finished=True)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT


def test_master_state_machine_orbit_finish_does_not_repeat_assistant_object_request() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()

    machine.step(orbit_finished=False)

    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert machine.poll_assistant_request() is None

    machine.step(orbit_finished=True)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() is None

    machine.step(orbit_finished=False)

    assert machine.poll_assistant_request() is None


def test_master_state_machine_emits_new_transport_task_request_after_orbit_finishes() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        assistant_object_arg=1,
        initial_context_id=0,
    )
    _enter_initial_search(machine)
    machine.poll_task_request()
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()

    machine.step(orbit_finished=True)

    assert _task_request(MasterStateMachine, machine.poll_task_request()) == {
        "context_id": 3,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 2,
    }


def test_master_state_machine_keeps_search_object_orbit_order() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    _enter_initial_search(machine)
    assert _task_request(MasterStateMachine, machine.poll_task_request()) == {
        "context_id": 1,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 1,
    }

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_object",
        "state": 2,
        "target": 1,
        "arg": _pack_task_arg(1, 2),
    }
    assert machine.poll_orbit_command() is None

    machine.mark_assistant_object_acknowledged()
    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert machine.poll_orbit_command() == 180.0

    machine.step(orbit_finished=False)
    assert machine.poll_assistant_request() is None

    machine.step(orbit_finished=True)
    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() is None

def test_master_state_machine_assistant_target_found_emits_assistant_orbit_once() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)

    machine.handle_assistant_target_found(value=300)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_orbit",
        "state": 3,
        "target": 1,
        "arg": _pack_task_arg(0, 2),
    }
    assert machine.poll_orbit_command() is None

    machine.handle_assistant_target_found(value=300)

    assert machine.poll_assistant_request() is None

def test_master_state_machine_exposes_search_velocity_gate() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    _enter_initial_search(machine)
    assert machine.allows_search_velocity() is True

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    assert machine.allows_search_velocity() is False
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)
    assert machine.allows_search_velocity() is True


def test_master_state_machine_does_not_enter_orbiting_before_assistant_ack() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_orbit_command() is None


def test_master_state_machine_ignores_master_aligned_before_front_half_completes() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        assistant_transport_arg=9,
    )

    _enter_initial_search(machine)
    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() is None


def test_master_state_machine_ignores_assistant_aligned_before_assistant_orbit_request() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        assistant_transport_arg=9,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)

    machine.handle_assistant_aligned(value=0)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() is None


def test_master_state_machine_buffers_assistant_target_found_until_orbit_finishes() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()

    machine.handle_assistant_target_found(value=300)

    assert machine.poll_assistant_request() is None

    machine.step(orbit_finished=True)

    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_orbit",
        "state": 3,
        "target": 1,
        "arg": _pack_task_arg(0, 2),
    }


def test_master_state_machine_does_not_enter_transport_until_both_sides_aligned() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() is None

    machine.handle_assistant_aligned(value=0)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_transport",
        "state": MasterStateMachine.ASSISTANT_TRANSPORT_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_TRANSPORT_SYNC_TARGET,
        "arg": _pack_task_arg(1, 2),
    }

    machine.mark_transport_ready()

    assert machine.state == MasterStateMachine.STATE_TRANSPORT_OBJECT


def test_master_state_machine_emits_assistant_transport_request_once() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_transport",
        "state": MasterStateMachine.ASSISTANT_TRANSPORT_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_TRANSPORT_SYNC_TARGET,
        "arg": _pack_task_arg(1, 2),
    }

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)

    assert machine.poll_assistant_request() is None


def test_master_state_machine_transport_requires_runtime_ready_signal() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.allows_search_velocity() is False

    machine.mark_transport_ready()

    assert machine.state == MasterStateMachine.STATE_TRANSPORT_OBJECT


def test_master_state_machine_master_aligned_disables_search_velocity_before_transport() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()
    machine.mark_assistant_object_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)

    assert machine.allows_search_velocity() is True

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.allows_search_velocity() is False


def test_master_state_machine_transport_ready_emits_finish_task() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)
    machine.poll_assistant_request()

    machine.mark_transport_ready()

    assert machine.state == MasterStateMachine.STATE_TRANSPORT_OBJECT
    assert _task_request(MasterStateMachine, machine.poll_task_request()) == {
        "kind": "finish_task",
        "context_id": 4,
        "state": MasterStateMachine.STATE_TRANSPORT_OBJECT,
        "target": MasterStateMachine.TARGET_EDGE_LINE,
        "arg": 3,
    }


def test_master_state_machine_finish_event_enters_clear_and_requests_assistant_clear() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)
    machine.poll_assistant_request()
    machine.mark_transport_ready()
    machine.poll_task_request()

    machine.handle_event(
        context_id=4, event=MasterStateMachine.EVENT_ARRIVED, value=0
    )

    assert machine.state == MasterStateMachine.STATE_CLEAR_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_clear",
        "state": MasterStateMachine.ASSISTANT_CLEAR_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_CLEAR_SYNC_TARGET,
        "arg": MasterStateMachine.CLEAR_PHASE_RETREAT,
    }


def test_master_state_machine_uses_object_target_edge_for_push_heading() -> None:
    """主车推动朝向由当前物体目标边推导."""
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    _enter_initial_search(machine)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=2
    )
    machine.poll_assistant_request()

    machine.mark_assistant_object_acknowledged()

    assert machine.poll_orbit_command() == 180.0


def test_master_state_machine_clear_retreat_waits_for_both_cars_before_turn_back() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)
    machine.poll_assistant_request()
    machine.mark_transport_ready()
    machine.poll_task_request()
    machine.handle_event(
        context_id=4, event=MasterStateMachine.EVENT_ARRIVED, value=0
    )
    machine.poll_assistant_request()

    machine.mark_master_cleared()

    assert machine.state == MasterStateMachine.STATE_CLEAR_OBJECT
    assert machine.poll_assistant_request() is None

    machine.handle_assistant_cleared(value=MasterStateMachine.CLEAR_PHASE_RETREAT)

    assert machine.state == MasterStateMachine.STATE_CLEAR_OBJECT
    assert machine.can_start_turn_back_rotation() is True
    assert machine.poll_assistant_request() is None


def test_master_state_machine_turn_back_completion_requests_forward_phase() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)
    machine.poll_assistant_request()
    machine.mark_transport_ready()
    machine.poll_task_request()
    machine.handle_event(
        context_id=4, event=MasterStateMachine.EVENT_ARRIVED, value=0
    )
    machine.poll_assistant_request()
    machine.mark_master_cleared()
    machine.handle_assistant_cleared(value=MasterStateMachine.CLEAR_PHASE_RETREAT)

    machine.mark_turn_back_completed()

    assert machine.state == MasterStateMachine.STATE_CLEAR_OBJECT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_clear",
        "state": MasterStateMachine.ASSISTANT_CLEAR_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_CLEAR_SYNC_TARGET,
        "arg": MasterStateMachine.CLEAR_PHASE_FORWARD,
    }


def test_master_state_machine_forward_completion_restarts_search_and_assistant_follow() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)
    machine.poll_assistant_request()
    machine.mark_transport_ready()
    machine.poll_task_request()
    machine.handle_event(
        context_id=4, event=MasterStateMachine.EVENT_ARRIVED, value=0
    )
    machine.poll_assistant_request()
    machine.mark_master_cleared()
    machine.handle_assistant_cleared(value=MasterStateMachine.CLEAR_PHASE_RETREAT)
    machine.mark_turn_back_completed()
    machine.poll_assistant_request()
    machine.mark_master_cleared()
    machine.handle_assistant_cleared(value=MasterStateMachine.CLEAR_PHASE_FORWARD)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert _task_request(MasterStateMachine, machine.poll_task_request()) == {
        "context_id": 5,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 1,
    }
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_follow",
        "state": MasterStateMachine.ASSISTANT_FOLLOW_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_FOLLOW_SYNC_TARGET,
        "arg": 0,
    }
    assert machine.allows_search_velocity() is False

    machine.mark_assistant_follow_acknowledged()

    assert machine.allows_search_velocity() is False

    machine.mark_restart_search_task_acknowledged()

    assert machine.allows_search_velocity() is True


def test_master_state_machine_forward_completion_enters_return_garage_when_all_objects_done() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)
    machine._obj_need = 1
    machine._ret_task_arg = 5
    machine._return_marker_task_arg = 6

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)
    machine.poll_assistant_request()
    machine.mark_transport_ready()
    machine.poll_task_request()
    machine.handle_event(
        context_id=4, event=MasterStateMachine.EVENT_ARRIVED, value=0
    )
    machine.poll_assistant_request()
    machine.mark_master_cleared()
    machine.handle_assistant_cleared(value=MasterStateMachine.CLEAR_PHASE_RETREAT)

    assert machine.obj_done == 1
    assert machine.state == MasterStateMachine.STATE_RETURN_GARAGE_RETREAT
    assert _assistant_request(MasterStateMachine, machine.poll_assistant_request()) == {
        "kind": "assistant_return_line",
        "state": MasterStateMachine.ASSISTANT_RETURN_FOLLOW_SYNC_STATE,
        "target": MasterStateMachine.ASSISTANT_RETURN_FOLLOW_SYNC_TARGET,
        "arg": 0,
    }
    assert _task_request(MasterStateMachine, machine.poll_task_request()) == {
        "kind": "return_line_task",
        "context_id": 5,
        "state": MasterStateMachine.STATE_RETURN_GARAGE_RETREAT,
        "target": MasterStateMachine.TARGET_EDGE_LINE,
        "arg": 5,
    }
    assert machine.poll_assistant_request() is None
    assert machine.allows_search_velocity() is False
    assert machine.allows_assistant_velocity_forward() is False


def test_master_state_machine_return_garage_events_do_not_advance_state() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        search_task_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
        total_object_count=1,
        return_line_task_arg=5,
        initial_context_id=4,
    )
    machine._restart_search_after_clear()
    machine.poll_assistant_request()
    line_task = machine.poll_task_request()

    machine.handle_event(
        context_id=line_task[MasterStateMachine.RQ_CONTEXT],
        event=MasterStateMachine.EVENT_RETURN_LINE_ALIGNED,
        value=0,
    )

    assert machine.state == MasterStateMachine.STATE_RETURN_GARAGE_RETREAT
    assert machine.poll_task_request() is None

    machine.handle_event(
        context_id=line_task[MasterStateMachine.RQ_CONTEXT],
        event=11,
        value=0,
    )

    assert machine.state == MasterStateMachine.STATE_RETURN_GARAGE_RETREAT
    assert machine.poll_task_request() is None

    machine.handle_event(
        context_id=line_task[MasterStateMachine.RQ_CONTEXT],
        event=12,
        value=0,
    )

    assert machine.state == MasterStateMachine.STATE_RETURN_GARAGE_RETREAT
    assert machine.poll_assistant_request() is None


def test_master_state_machine_restart_search_waits_both_follow_and_local_task_ack() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = _drive_machine_to_post_assistant_orbit_request(MasterStateMachine)

    machine.handle_event(
        context_id=3, event=MasterStateMachine.EVENT_ALIGNED, value=0
    )
    machine.handle_assistant_aligned(value=0)
    machine.poll_assistant_request()
    machine.mark_transport_ready()
    machine.poll_task_request()
    machine.handle_event(
        context_id=4, event=MasterStateMachine.EVENT_ARRIVED, value=0
    )
    machine.poll_assistant_request()
    machine.mark_master_cleared()
    machine.handle_assistant_cleared(value=MasterStateMachine.CLEAR_PHASE_RETREAT)
    machine.mark_turn_back_completed()
    machine.poll_assistant_request()
    machine.mark_master_cleared()
    machine.handle_assistant_cleared(value=MasterStateMachine.CLEAR_PHASE_FORWARD)
    machine.poll_task_request()
    machine.poll_assistant_request()

    machine.mark_assistant_follow_acknowledged()

    assert machine.allows_search_velocity() is False

    machine.mark_restart_search_task_acknowledged()

    assert machine.allows_search_velocity() is True
