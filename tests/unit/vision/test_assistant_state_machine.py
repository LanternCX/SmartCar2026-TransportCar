"""辅车子状态机纯逻辑测试."""

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))


def _load_assistant_state_machine():
    module_path = SRC / "vision" / "assistant" / "state_machine.py"
    spec = importlib.util.spec_from_file_location(
        "test_assistant_state_machine_module", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load assistant state machine module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_assistant_state_constants_are_owned_by_vision_layer() -> None:
    module = _load_assistant_state_machine()

    assert module.ASSISTANT_STATE_IDLE == 0
    assert module.ASSISTANT_STATE_FOLLOW == 1
    assert module.ASSISTANT_STATE_APPROACH_OBJECT == 2
    assert module.ASSISTANT_STATE_CLEAR_OBJECT == 5
    assert module.ASSISTANT_TARGET_NONE == 0
    assert module.ASSISTANT_TARGET_OBJECT == 1


def test_assistant_state_machine_defaults_to_follow() -> None:
    module = _load_assistant_state_machine()

    machine = module.AssistantStateMachine()

    assert machine.state == module.ASSISTANT_STATE_FOLLOW
    assert machine.is_idle() is False


def test_assistant_state_machine_accepts_idle_command() -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(
        module.ASSISTANT_STATE_IDLE,
        module.ASSISTANT_TARGET_NONE,
        0,
    )

    assert applied is True
    assert machine.state == module.ASSISTANT_STATE_IDLE
    assert machine.is_idle() is True


def test_assistant_state_machine_prints_when_entering_new_state(capsys) -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(
        module.ASSISTANT_STATE_IDLE,
        module.ASSISTANT_TARGET_NONE,
        0,
    )

    assert applied is True
    assert capsys.readouterr().out.endswith("assistant_state: IDLE\n")


def test_assistant_state_machine_accepts_approach_object_command() -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(
        module.ASSISTANT_STATE_APPROACH_OBJECT,
        module.ASSISTANT_TARGET_OBJECT,
        7,
    )

    assert applied is True
    assert machine.state == module.ASSISTANT_STATE_APPROACH_OBJECT
    assert machine.target == module.ASSISTANT_TARGET_OBJECT
    assert machine.arg == 7


def test_assistant_state_machine_accepts_transport_object_command() -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(
        module.ASSISTANT_STATE_TRANSPORT_OBJECT,
        module.ASSISTANT_TARGET_OBJECT,
        9,
    )

    assert applied is True
    assert machine.state == module.ASSISTANT_STATE_TRANSPORT_OBJECT
    assert machine.target == module.ASSISTANT_TARGET_OBJECT
    assert machine.arg == 9


def test_assistant_state_machine_accepts_clear_object_command() -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(
        module.ASSISTANT_STATE_CLEAR_OBJECT,
        module.ASSISTANT_TARGET_OBJECT,
        0,
    )

    assert applied is True
    assert machine.state == module.ASSISTANT_STATE_CLEAR_OBJECT
    assert machine.target == module.ASSISTANT_TARGET_OBJECT
    assert machine.arg == 0


def test_assistant_state_machine_rejects_approach_object_with_non_object_target() -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(
        module.ASSISTANT_STATE_APPROACH_OBJECT,
        module.ASSISTANT_TARGET_NONE,
        7,
    )

    assert applied is False
    assert machine.state == module.ASSISTANT_STATE_FOLLOW
    assert machine.target == module.ASSISTANT_TARGET_NONE
    assert machine.arg == 0


def test_assistant_state_machine_rejects_transport_object_with_non_object_target() -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(
        module.ASSISTANT_STATE_TRANSPORT_OBJECT,
        module.ASSISTANT_TARGET_NONE,
        9,
    )

    assert applied is False
    assert machine.state == module.ASSISTANT_STATE_FOLLOW
    assert machine.target == module.ASSISTANT_TARGET_NONE
    assert machine.arg == 0


def test_assistant_state_machine_ignores_unknown_state() -> None:
    module = _load_assistant_state_machine()
    machine = module.AssistantStateMachine()

    applied = machine.apply_master_state(99, module.ASSISTANT_TARGET_NONE, 0)

    assert applied is False
    assert machine.state == module.ASSISTANT_STATE_FOLLOW
