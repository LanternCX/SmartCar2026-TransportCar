"""! @brief 主车搜索状态机纯逻辑测试"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from vision.master.state_machine import (  # noqa: E402
    EVENT_TARGET_FOUND,
    OBJECT_FOUND,
    SEARCH_OBJECT,
    TARGET_OBJECT,
    MasterSearchStateMachine,
)


def _build_machine():
    return MasterSearchStateMachine(hook_config_id=5)


def test_enter_search_creates_hook_sync_context() -> None:
    """! @brief 进入搜索态时创建视觉 hook 同步上下文"""

    machine = _build_machine()

    sync = machine.enter_search()

    assert machine.state == SEARCH_OBJECT
    assert sync == {
        "reliable_seq": 1,
        "context_id": 1,
        "state": SEARCH_OBJECT,
        "target": TARGET_OBJECT,
        "arg": 5,
    }


def test_state_machine_does_not_generate_search_velocity() -> None:
    """! @brief 状态机只维护搜索上下文和事件, 不提供速度生成入口"""

    machine = _build_machine()

    assert not hasattr(machine, "build_velocity")


def test_state_machine_does_not_consume_observation_packets() -> None:
    """! @brief 状态机只处理可靠事件, 不消费视觉观测包"""

    machine = _build_machine()

    assert not hasattr(machine, "handle_observation")
    assert not hasattr(machine, "last_observation")


def test_target_found_event_requires_matching_context_and_is_idempotent() -> None:
    """! @brief TARGET_FOUND 只接受匹配上下文, 重复事件不重复迁移"""

    machine = _build_machine()
    machine.enter_search()

    assert machine.handle_event({"context_id": 2, "event": EVENT_TARGET_FOUND, "value": 99}) is False
    assert machine.state == SEARCH_OBJECT
    assert machine.transition_count == 0

    assert machine.handle_event({"context_id": 1, "event": EVENT_TARGET_FOUND, "value": 99}) is True
    assert machine.state == OBJECT_FOUND
    assert machine.transition_count == 1

    assert machine.handle_event({"context_id": 1, "event": EVENT_TARGET_FOUND, "value": 99}) is False
    assert machine.state == OBJECT_FOUND
    assert machine.transition_count == 1
