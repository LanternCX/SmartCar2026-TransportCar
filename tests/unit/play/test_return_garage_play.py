"""主辅回库 Play 结构测试."""

from play.routines.assistant_return_garage import (
    ASSISTANT_LEAD_DISTANCE,
    FINAL_FORWARD_SPEED as ASSISTANT_FINAL_FORWARD_SPEED,
    RETURN_POSITION_SPEED as ASSISTANT_RETURN_POSITION_SPEED,
    RETURN_FORWARD_SPEED as ASSISTANT_RETURN_FORWARD_SPEED,
    AssistantReturnGaragePlay,
)
from play.routines.master_return_garage import (
    FINAL_FORWARD_SPEED as MASTER_FINAL_FORWARD_SPEED,
    MASTER_LEAD_DISTANCE,
    RETURN_POSITION_SPEED as MASTER_RETURN_POSITION_SPEED,
    RETURN_FORWARD_SPEED as MASTER_RETURN_FORWARD_SPEED,
    MasterReturnGaragePlay,
)
from play.steps import AngleStep, PositionYStep, VelocityYStep


def test_master_return_garage_play_declares_expected_steps() -> None:
    play = MasterReturnGaragePlay()

    assert len(play._steps) == 5
    assert isinstance(play._steps[0], PositionYStep)
    assert play._steps[0].target == MASTER_LEAD_DISTANCE
    assert play._steps[0].max_speed_cmd == MASTER_RETURN_POSITION_SPEED
    assert isinstance(play._steps[1], AngleStep)
    assert play._steps[1].target == 90.0
    assert isinstance(play._steps[2], VelocityYStep)
    assert play._steps[2].speed == MASTER_RETURN_FORWARD_SPEED
    assert callable(play._steps[2].until)
    assert isinstance(play._steps[3], AngleStep)
    assert play._steps[3].target == -90.0
    assert isinstance(play._steps[4], VelocityYStep)
    assert play._steps[4].speed == MASTER_FINAL_FORWARD_SPEED
    assert play._steps[4].until is None


def test_assistant_return_garage_play_declares_expected_steps() -> None:
    play = AssistantReturnGaragePlay()

    assert len(play._steps) == 5
    assert isinstance(play._steps[0], PositionYStep)
    assert play._steps[0].target == ASSISTANT_LEAD_DISTANCE
    assert play._steps[0].max_speed_cmd == ASSISTANT_RETURN_POSITION_SPEED
    assert isinstance(play._steps[1], AngleStep)
    assert play._steps[1].target == -90.0
    assert isinstance(play._steps[2], VelocityYStep)
    assert play._steps[2].speed == ASSISTANT_RETURN_FORWARD_SPEED
    assert callable(play._steps[2].until)
    assert isinstance(play._steps[3], AngleStep)
    assert play._steps[3].target == -90.0
    assert isinstance(play._steps[4], VelocityYStep)
    assert play._steps[4].speed == ASSISTANT_FINAL_FORWARD_SPEED
    assert play._steps[4].until is None


def test_startup_move_play_declares_forward_turn_forward_turn_steps() -> None:
    from play.routines import startup_move

    StartupMovePlay = startup_move.StartupMovePlay
    play = StartupMovePlay()

    assert len(play._steps) == 4
    assert isinstance(play._steps[0], PositionYStep)
    assert play._steps[0].target == startup_move.STARTUP_FIRST_FORWARD_DISTANCE
    assert play._steps[0].max_speed_cmd == startup_move.STARTUP_MOVE_SPEED
    assert isinstance(play._steps[1], AngleStep)
    assert play._steps[1].target == startup_move.STARTUP_RIGHT_TURN_DEG
    assert isinstance(play._steps[2], PositionYStep)
    assert play._steps[2].target == startup_move.STARTUP_SECOND_FORWARD_DISTANCE
    assert play._steps[2].max_speed_cmd == startup_move.STARTUP_MOVE_SPEED
    assert isinstance(play._steps[3], AngleStep)
    assert play._steps[3].target == startup_move.STARTUP_LEFT_TURN_DEG
