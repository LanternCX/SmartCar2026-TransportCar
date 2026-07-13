"""启动 Play 流程测试。"""

from play.routines import OP_ANGLE, OP_END, OP_POS_Y
from play.routines import startup_move


def test_master_startup_ends_after_second_forward_segment() -> None:
    """主车首次转向后执行第二段前进并结束启动 Play."""

    assert startup_move.SEQUENCE[3] == OP_ANGLE
    assert startup_move.SEQUENCE[6] == OP_POS_Y
    assert startup_move.SEQUENCE[9] == OP_END


def test_assistant_startup_ends_after_first_right_turn() -> None:
    """辅车右转完成后结束启动 Play."""

    assert startup_move.ASSISTANT_SEQUENCE[3] == OP_ANGLE
    assert startup_move.ASSISTANT_SEQUENCE[6] == OP_END
