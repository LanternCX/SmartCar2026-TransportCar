"""主车状态机纯逻辑测试."""

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from protocol.state import (  # noqa: E402
    EVENT_TARGET_FOUND,
    STATE_IDLE,
    STATE_ORBITING,
    STATE_SEARCH_OBJECT,
    TARGET_OBJECT,
)


def _load_master_state_machine():
    module_path = SRC / "vision" / "master" / "state_machine.py"
    spec = importlib.util.spec_from_file_location("test_master_state_machine_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load master state machine module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MasterStateMachine


def test_master_state_machine_enters_search_and_builds_hook_context() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    machine.step(orbit_finished=False)
    hook_request = machine.poll_hook_request()

    assert machine.state == STATE_SEARCH_OBJECT
    assert hook_request == {
        "context_id": 1,
        "state": STATE_SEARCH_OBJECT,
        "target": TARGET_OBJECT,
        "arg": 1,
    }


def test_master_state_machine_matching_target_found_enters_orbiting() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)

    machine.handle_event(context_id=1, event=EVENT_TARGET_FOUND, value=300)
    orbit_command = machine.poll_orbit_command()

    assert machine.state == STATE_ORBITING
    assert orbit_command == {
        "target_heading_deg": 105.0,
    }


def test_master_state_machine_ignores_mismatched_context_event() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)

    machine.handle_event(context_id=9, event=EVENT_TARGET_FOUND, value=300)

    assert machine.state == STATE_SEARCH_OBJECT
    assert machine.poll_orbit_command() is None


def test_master_state_machine_does_not_repeat_orbit_enter_action() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)

    machine.handle_event(context_id=1, event=EVENT_TARGET_FOUND, value=300)
    first_orbit_command = machine.poll_orbit_command()
    machine.handle_event(context_id=1, event=EVENT_TARGET_FOUND, value=300)

    assert first_orbit_command == {"target_heading_deg": 105.0}
    assert machine.poll_orbit_command() is None


def test_master_state_machine_returns_to_idle_when_orbit_finishes() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )
    machine.step(orbit_finished=False)
    machine.handle_event(context_id=1, event=EVENT_TARGET_FOUND, value=300)
    machine.poll_orbit_command()

    machine.step(orbit_finished=True)

    assert machine.state == STATE_IDLE


def test_master_state_machine_exposes_search_velocity_gate() -> None:
    MasterStateMachine = _load_master_state_machine()
    machine = MasterStateMachine(
        hook_arg=1,
        boot_heading_deg=15.0,
        orbit_delta_deg=90.0,
    )

    machine.step(orbit_finished=False)
    assert machine.allows_search_velocity() is True

    machine.handle_event(context_id=1, event=EVENT_TARGET_FOUND, value=300)
    assert machine.allows_search_velocity() is False
