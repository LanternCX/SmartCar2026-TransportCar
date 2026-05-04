"""主车状态机纯逻辑测试."""

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

def _load_master_state_machine():
    module_path = SRC / "vision" / "master" / "state_machine.py"
    spec = importlib.util.spec_from_file_location("test_master_state_machine_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load master state machine module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_master_state_machine_enters_search_and_builds_hook_context() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    machine.step(orbit_finished=False)
    hook_request = machine.poll_hook_request()

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert hook_request == {
        "context_id": 1,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 1,
    }


def test_master_state_machine_matching_target_found_enters_orbiting() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    assistant_request = machine.poll_assistant_request()
    orbit_command = machine.poll_orbit_command()

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert assistant_request == {
        "kind": "assistant_idle",
        "state": 0,
        "target": 0,
        "arg": 0,
    }
    assert orbit_command is None



def test_master_state_machine_marks_assistant_idle_request_kind() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )

    assert machine.poll_assistant_request() == {
        "kind": "assistant_idle",
        "state": 0,
        "target": 0,
        "arg": 0,
    }


def test_master_state_machine_marks_assistant_object_request_kind() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    machine.poll_assistant_request()
    machine.mark_assistant_idle_acknowledged()
    machine.poll_orbit_command()

    machine.step(orbit_finished=True)

    assert machine.poll_assistant_request() == {
        "kind": "assistant_object",
        "state": 2,
        "target": 1,
        "arg": 1,
    }


def test_master_state_machine_marks_assistant_orbit_request_kind() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    machine.poll_assistant_request()
    machine.mark_assistant_idle_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)
    machine.poll_assistant_request()

    machine.handle_assistant_target_found(value=300)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() == {
        "kind": "assistant_orbit",
        "state": 3,
        "target": 1,
        "arg": 0,
    }

def test_master_state_machine_enters_orbiting_after_assistant_idle_ack() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    machine.poll_assistant_request()

    machine.mark_assistant_idle_acknowledged()
    orbit_command = machine.poll_orbit_command()

    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert orbit_command == {
        "target_heading_deg": 105.0,
    }


def test_master_state_machine_ignores_mismatched_context_event() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)

    machine.handle_event(
        context_id=9, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() is None
    assert machine.poll_orbit_command() is None


def test_master_state_machine_does_not_repeat_orbit_enter_action() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    first_assistant_request = machine.poll_assistant_request()
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )

    assert first_assistant_request == {
        "kind": "assistant_idle",
        "state": 0,
        "target": 0,
        "arg": 0,
    }
    assert machine.poll_assistant_request() is None
    assert machine.poll_orbit_command() is None


def test_master_state_machine_returns_to_search_when_orbit_finishes() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    machine.poll_assistant_request()
    machine.mark_assistant_idle_acknowledged()
    machine.poll_orbit_command()

    machine.step(orbit_finished=True)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT


def test_master_state_machine_emits_assistant_object_request_once_after_orbit_finishes() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    machine.poll_assistant_request()
    machine.mark_assistant_idle_acknowledged()
    machine.poll_orbit_command()

    machine.step(orbit_finished=False)

    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert machine.poll_assistant_request() is None

    machine.step(orbit_finished=True)
    assistant_request = machine.poll_assistant_request()

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert assistant_request == {
        "kind": "assistant_object",
        "state": 2,
        "target": 1,
        "arg": 1,
    }

    machine.step(orbit_finished=False)

    assert machine.poll_assistant_request() is None


def test_master_state_machine_keeps_search_stop_orbit_and_assistant_object_order() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    machine.step(orbit_finished=False)
    assert machine.poll_hook_request() == {
        "context_id": 1,
        "state": MasterStateMachine.STATE_SEARCH_OBJECT,
        "target": MasterStateMachine.TARGET_OBJECT,
        "arg": 1,
    }

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    assert machine.poll_assistant_request() == {
        "kind": "assistant_idle",
        "state": 0,
        "target": 0,
        "arg": 0,
    }
    assert machine.poll_orbit_command() is None

    machine.mark_assistant_idle_acknowledged()
    assert machine.state == MasterStateMachine.STATE_ORBITING
    assert machine.poll_orbit_command() == {
        "target_heading_deg": 105.0,
    }

    machine.step(orbit_finished=False)
    assert machine.poll_assistant_request() is None

    machine.step(orbit_finished=True)
    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() == {
        "kind": "assistant_object",
        "state": 2,
        "target": 1,
        "arg": 1,
    }

def test_master_state_machine_assistant_target_found_emits_assistant_orbit_once() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    machine.poll_assistant_request()
    machine.mark_assistant_idle_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)
    machine.poll_assistant_request()

    machine.handle_assistant_target_found(value=300)

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_assistant_request() == {
        "kind": "assistant_orbit",
        "state": 3,
        "target": 1,
        "arg": 0,
    }
    assert machine.poll_orbit_command() is None

    machine.handle_assistant_target_found(value=300)

    assert machine.poll_assistant_request() is None

def test_master_state_machine_exposes_search_velocity_gate() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    machine.step(orbit_finished=False)
    assert machine.allows_search_velocity() is True

    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )
    assert machine.allows_search_velocity() is False
    machine.poll_assistant_request()
    machine.mark_assistant_idle_acknowledged()
    machine.poll_orbit_command()
    machine.step(orbit_finished=True)
    machine.poll_assistant_request()
    assert machine.allows_search_velocity() is True


def test_master_state_machine_does_not_enter_orbiting_before_assistant_ack() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine.MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    machine.step(orbit_finished=False)
    machine.handle_event(
        context_id=1, event=MasterStateMachine.EVENT_TARGET_FOUND, value=300
    )

    assert machine.state == MasterStateMachine.STATE_SEARCH_OBJECT
    assert machine.poll_orbit_command() is None
