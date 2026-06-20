"""主辅回库 Play 结构测试."""

from play.routines.assistant_return_garage import (
    ASSISTANT_LEAD_DISTANCE,
    FINAL_FORWARD_SPEED as ASSISTANT_FINAL_FORWARD_SPEED,
    RETURN_FORWARD_SPEED as ASSISTANT_RETURN_FORWARD_SPEED,
    AssistantReturnGaragePlay,
)
from play.routines.master_return_garage import (
    FINAL_FORWARD_SPEED as MASTER_FINAL_FORWARD_SPEED,
    MASTER_LEAD_DISTANCE,
    RETURN_FORWARD_SPEED as MASTER_RETURN_FORWARD_SPEED,
    MasterReturnGaragePlay,
)
from play.steps import AngleStep, PositionYStep, VelocityYStep


def test_master_return_garage_play_declares_expected_steps() -> None:
    play = MasterReturnGaragePlay()

    assert len(play._steps) == 5
    assert isinstance(play._steps[0], PositionYStep)
    assert play._steps[0].target == MASTER_LEAD_DISTANCE
    assert isinstance(play._steps[1], AngleStep)
    assert play._steps[1].target == 90.0
    assert isinstance(play._steps[2], VelocityYStep)
    assert play._steps[2].speed == 5.0
    assert callable(play._steps[2].until)
    assert isinstance(play._steps[3], AngleStep)
    assert play._steps[3].target == -90.0
    assert isinstance(play._steps[4], VelocityYStep)
    assert play._steps[4].speed == 3.0
    assert play._steps[4].until is None
    assert MASTER_RETURN_FORWARD_SPEED == 5
    assert MASTER_FINAL_FORWARD_SPEED == 3


def test_assistant_return_garage_play_declares_expected_steps() -> None:
    play = AssistantReturnGaragePlay()

    assert len(play._steps) == 5
    assert isinstance(play._steps[0], PositionYStep)
    assert play._steps[0].target == ASSISTANT_LEAD_DISTANCE
    assert isinstance(play._steps[1], AngleStep)
    assert play._steps[1].target == -90.0
    assert isinstance(play._steps[2], VelocityYStep)
    assert play._steps[2].speed == 5.0
    assert callable(play._steps[2].until)
    assert isinstance(play._steps[3], AngleStep)
    assert play._steps[3].target == -90.0
    assert isinstance(play._steps[4], VelocityYStep)
    assert play._steps[4].speed == 3.0
    assert play._steps[4].until is None
    assert ASSISTANT_RETURN_FORWARD_SPEED == 5
    assert ASSISTANT_FINAL_FORWARD_SPEED == 3
