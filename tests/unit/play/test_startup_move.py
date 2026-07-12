"""启动 Play 流程测试。"""

from play.routines import OP_ANGLE, OP_END, OP_POS_Y
from play.routines import startup_move


def test_startup_turns_use_field_absolute_heading() -> None:
    """启动流程只转向一次并保持向 right 的绝对朝向。"""

    assert startup_move.SEQUENCE[3] == OP_ANGLE
    assert startup_move.SEQUENCE[4] == 90
    assert startup_move.SEQUENCE[9] == OP_END


def test_master_startup_moves_forward_ninety_centimeters_after_turn() -> None:
    """主车右转后固定前进九十厘米."""

    assert startup_move.SEQUENCE[6] == OP_POS_Y
    assert startup_move.SEQUENCE[7] == 90


def test_assistant_startup_ends_after_first_right_turn() -> None:
    """辅车右转完成后结束启动 Play."""

    assert startup_move.ASSISTANT_SEQUENCE[3] == OP_ANGLE
    assert startup_move.ASSISTANT_SEQUENCE[4] == 90
    assert startup_move.ASSISTANT_SEQUENCE[6] == OP_END
