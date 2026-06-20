"""Play 步骤行为测试."""

from play.steps import (
    AngleStep,
    PositionYStep,
    VelocityXStep,
    VelocityYStep,
    VelocityWStep,
    PositionXStep,
)


class _FakeContext:
    def __init__(self):
        self.events = []
        self.position_y_done = False
        self.angle_done = False
        self.yellow_ready = False

    def set_position_y(self, value):
        self.events.append(("position_y", float(value)))

    def set_angle(self, value):
        self.events.append(("angle", float(value)))

    def write_velocity_y(self, value):
        self.events.append(("velocity_y", float(value)))

    def is_position_y_done(self):
        return self.position_y_done

    def is_angle_done(self):
        return self.angle_done

    def yellow_line_ready(self):
        return self.yellow_ready

    def set_position_x(self, value):
        self.events.append(("position_x", float(value)))

    def write_velocity_x(self, value):
        self.events.append(("velocity_x", float(value)))

    def write_omega(self, value):
        self.events.append(("omega", float(value)))

    def is_position_x_done(self):
        return self.position_y_done


def test_position_y_step_writes_target_only_once_and_waits_done() -> None:
    ctx = _FakeContext()
    step = PositionYStep(0.3)

    first = step.tick(ctx)
    second = step.tick(ctx)

    assert first == "waiting"
    assert second == "waiting"
    assert ctx.events == [("position_y", 0.3)]

    ctx.position_y_done = True

    third = step.tick(ctx)

    assert third == "finished"
    assert ctx.events == [("position_y", 0.3)]


def test_angle_step_writes_target_only_once_and_waits_done() -> None:
    ctx = _FakeContext()
    step = AngleStep(90)

    first = step.tick(ctx)
    second = step.tick(ctx)

    assert first == "waiting"
    assert second == "waiting"
    assert ctx.events == [("angle", 90.0)]

    ctx.angle_done = True

    third = step.tick(ctx)

    assert third == "finished"
    assert ctx.events == [("angle", 90.0)]


def test_velocity_y_step_writes_fixed_speed_every_tick_until_callback_returns_true() -> None:
    ctx = _FakeContext()
    step = VelocityYStep(5, until=lambda current_ctx: current_ctx.yellow_line_ready())

    first = step.tick(ctx)
    second = step.tick(ctx)

    assert first == "running"
    assert second == "running"
    assert ctx.events == [("velocity_y", 5.0), ("velocity_y", 5.0)]

    ctx.yellow_ready = True

    third = step.tick(ctx)

    assert third == "finished"
    assert ctx.events == [
        ("velocity_y", 5.0),
        ("velocity_y", 5.0),
        ("velocity_y", 5.0),
    ]


def test_velocity_y_step_calls_on_enter_only_once() -> None:
    ctx = _FakeContext()
    enter_calls = []
    step = VelocityYStep(
        5,
        until=lambda current_ctx: current_ctx.yellow_line_ready(),
        on_enter=lambda current_ctx: enter_calls.append(current_ctx),
    )

    step.tick(ctx)
    step.tick(ctx)

    assert enter_calls == [ctx]


def test_position_y_step_calls_on_exit_when_finished() -> None:
    ctx = _FakeContext()
    exit_calls = []
    step = PositionYStep(0.3, on_exit=lambda current_ctx: exit_calls.append(current_ctx))

    step.tick(ctx)
    ctx.position_y_done = True
    step.tick(ctx)

    assert exit_calls == [ctx]


def test_velocity_y_step_calls_on_exit_when_until_becomes_true() -> None:
    ctx = _FakeContext()
    exit_calls = []
    step = VelocityYStep(
        5,
        until=lambda current_ctx: current_ctx.yellow_line_ready(),
        on_exit=lambda current_ctx: exit_calls.append(current_ctx),
    )

    step.tick(ctx)
    ctx.yellow_ready = True
    step.tick(ctx)

    assert exit_calls == [ctx]


def test_all_base_step_subclasses_accept_enter_and_exit_hooks() -> None:
    enter = lambda ctx: None
    exit_ = lambda ctx: None

    steps = (
        PositionXStep(0.1, on_enter=enter, on_exit=exit_),
        PositionYStep(0.1, on_enter=enter, on_exit=exit_),
        AngleStep(90, on_enter=enter, on_exit=exit_),
        VelocityXStep(1, on_enter=enter, on_exit=exit_),
        VelocityYStep(1, on_enter=enter, on_exit=exit_),
        VelocityWStep(1, on_enter=enter, on_exit=exit_),
    )

    assert len(steps) == 6


def test_velocity_x_step_without_until_enters_holding_and_keeps_writing_speed() -> None:
    ctx = _FakeContext()
    step = VelocityXStep(3)

    first = step.tick(ctx)
    second = step.tick(ctx)

    assert first == "holding"
    assert second == "holding"
    assert ctx.events == [("velocity_x", 3.0), ("velocity_x", 3.0)]


def test_velocity_y_step_without_until_enters_holding_and_keeps_writing_speed() -> None:
    ctx = _FakeContext()
    step = VelocityYStep(3)

    first = step.tick(ctx)
    second = step.tick(ctx)

    assert first == "holding"
    assert second == "holding"
    assert ctx.events == [("velocity_y", 3.0), ("velocity_y", 3.0)]


def test_velocity_w_step_without_until_enters_holding_and_keeps_writing_speed() -> None:
    ctx = _FakeContext()
    step = VelocityWStep(3)

    first = step.tick(ctx)
    second = step.tick(ctx)

    assert first == "holding"
    assert second == "holding"
    assert ctx.events == [("omega", 3.0), ("omega", 3.0)]
