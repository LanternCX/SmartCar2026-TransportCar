"""启动 Play 流程测试。"""

from play.routines import OP_ANGLE
from play.routines import startup_move


def test_startup_turns_use_field_absolute_heading() -> None:
    """启动转向使用固定场地绝对朝向。"""

    assert startup_move.SEQUENCE[3] == OP_ANGLE
    assert startup_move.SEQUENCE[4] == 90
    assert startup_move.SEQUENCE[9] == OP_ANGLE
    assert startup_move.SEQUENCE[10] == 0
