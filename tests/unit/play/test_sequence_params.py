"""Play 启动参数行为测试."""

from play import sequence


class _Runtime:
    def __init__(self) -> None:
        self.play_kind = 0
        self.play_step = 0
        self.play_entered = False
        self.play_params = None
        self.motion_done = False
        self.events = []

    def play_set_position_y(self, value, max_speed_cmd=None) -> None:
        assert max_speed_cmd is not None
        self.events.append(("position_y", float(value), int(max_speed_cmd)))
        self.motion_done = False

    def play_set_angle(self, value) -> None:
        self.events.append(("angle", float(value)))
        self.motion_done = False

    def play_motion_done(self) -> bool:
        return self.motion_done

    def play_clear_yellow_line_ready(self) -> None:
        return None

    def play_enable_yellow_line_ready_gate(self) -> None:
        return None

    def play_disable_yellow_line_ready_gate(self) -> None:
        return None

    def play_write_velocity_y(self, value) -> None:
        self.events.append(("velocity_y", float(value)))

    def play_yellow_line_ready(self) -> bool:
        return False


def test_return_play_uses_startup_distance_and_angle_parameters() -> None:
    """回库 Play 从启动参数读取相对位移和绝对角度."""
    runtime = _Runtime()

    sequence.start(
        runtime,
        sequence.PLAY_MASTER_RETURN,
        (-25.5, -153.4349488),
    )
    sequence.tick(runtime)

    assert runtime.events == [("position_y", -0.255, 5)]
    runtime.motion_done = True

    sequence.tick(runtime)

    assert runtime.events[-1] == ("angle", -153.4349488)


def test_static_play_starts_without_parameters() -> None:
    """静态 Play 不注入参数时继续读取序列内固定值."""
    runtime = _Runtime()

    sequence.start(runtime, sequence.PLAY_STARTUP)
    sequence.tick(runtime)

    assert runtime.events == [("position_y", 0.7, 5)]
