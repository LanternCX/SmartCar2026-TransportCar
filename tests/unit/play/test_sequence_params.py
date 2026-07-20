"""Play 启动参数行为测试."""

from play import sequence
from play.routines import master_return_garage, startup_move


class _Runtime:
    def __init__(self) -> None:
        self.play_kind = 0
        self.play_step = 0
        self.play_entered = False
        self.play_params = None
        self.motion_done = False
        self.line_ready = False
        self.events = []

    def play_set_position_y(self, value, max_speed_cmd=None) -> None:
        assert max_speed_cmd is not None
        self.events.append(("position_y", float(value), int(max_speed_cmd)))
        self.motion_done = False

    def play_set_position_xy(self, x, y, max_speed_cmd=None) -> None:
        assert max_speed_cmd is not None
        self.events.append(("position", float(x), float(y), int(max_speed_cmd)))
        self.motion_done = False

    def play_set_angle(self, value) -> None:
        self.events.append(("angle", float(value)))
        self.motion_done = False

    def play_motion_done(self) -> bool:
        return self.motion_done

    def play_clear_line_ready(self) -> None:
        return None

    def play_write_velocity_y(self, value) -> None:
        self.events.append(("velocity_y", float(value)))

    def play_line_ready(self) -> bool:
        return self.line_ready


def test_return_play_uses_startup_distance_and_angle_parameters() -> None:
    """回库 Play 从启动参数读取相对位移和绝对角度."""
    runtime = _Runtime()

    sequence.start(
        runtime,
        sequence.PLAY_MASTER_RETURN,
        (-25.5, -153.4349488),
    )
    sequence.tick(runtime)

    assert runtime.events == [
        ("position_y", -0.255, int(master_return_garage.SEQUENCE[2]))
    ]
    runtime.motion_done = True

    sequence.tick(runtime)

    assert runtime.events[-1] == ("angle", -153.4349488)


def test_return_plays_retreat_after_reaching_left_line() -> None:
    """主辅车寻到 left 边后先后退八厘米再转向."""
    for kind in (sequence.PLAY_MASTER_RETURN, sequence.PLAY_ASSISTANT_RETURN):
        runtime = _Runtime()
        sequence.start(runtime, kind, (-25.5, -90.0))
        sequence.tick(runtime)
        runtime.motion_done = True
        sequence.tick(runtime)
        runtime.motion_done = True
        sequence.tick(runtime)
        runtime.line_ready = True
        sequence.tick(runtime)

        assert runtime.events[-1] == (
            "position_y",
            -0.08,
            int(master_return_garage._RETURN_POSITION_SPEED),
        )


def test_startup_play_uses_planned_absolute_position() -> None:
    """启动 Play 从启动参数读取第一段世界系绝对目标点."""
    runtime = _Runtime()

    sequence.start(runtime, sequence.PLAY_STARTUP, ((10.0, 45.0),))
    sequence.tick(runtime)

    assert runtime.events == [
        ("position", 0.1, 0.45, int(startup_move.SEQUENCE[2]))
    ]


def test_assistant_startup_finishes_immediately_after_right_turn() -> None:
    """辅车启动 Play 不执行主车的第二段固定前进."""
    runtime = _Runtime()

    sequence.start(
        runtime,
        sequence.PLAY_ASSISTANT_STARTUP,
        ((10.0, 45.0),),
    )
    sequence.tick(runtime)
    runtime.motion_done = True
    sequence.tick(runtime)
    runtime.motion_done = True

    assert sequence.tick(runtime) is True
    assert runtime.events == [
        ("position", 0.1, 0.45, int(startup_move.ASSISTANT_SEQUENCE[2])),
        ("angle", float(startup_move.ASSISTANT_SEQUENCE[4])),
    ]
