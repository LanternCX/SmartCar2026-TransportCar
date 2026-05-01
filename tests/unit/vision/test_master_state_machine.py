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
    return MasterSearchStateMachine(
        search_vx=0.12,
        search_vy=-0.03,
        hook_config_id=5,
    )


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


def test_search_and_found_velocity_outputs() -> None:
    """! @brief 搜索态输出固定平移量, 找到后输出零速度"""

    machine = _build_machine()
    machine.enter_search()

    assert machine.build_velocity() == (0.12, -0.03)

    machine.handle_event({"context_id": 1, "event": EVENT_TARGET_FOUND, "value": 99})

    assert machine.state == OBJECT_FOUND
    assert machine.build_velocity() == (0.0, 0.0)


def test_observation_only_records_matching_context_without_state_jump() -> None:
    """! @brief 观测包只记录匹配上下文, 不在车端判断 hook 命中"""

    machine = _build_machine()
    machine.enter_search()

    assert machine.handle_observation({"context_id": 2, "x": 0.0, "y": 0.0, "value": 99.0}) is False
    assert machine.last_observation is None

    assert machine.handle_observation({"context_id": 1, "x": 0.0, "y": 0.0, "value": 99.0}) is False
    assert machine.last_observation == {"context_id": 1, "x": 0.0, "y": 0.0, "value": 99.0}
    assert machine.state == SEARCH_OBJECT


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
