"""PlayRunner 行为测试."""

from play.base import BasePlay
from play.runner import PlayRunner


class _IdleContext:
    pass


class _FinishStep:
    def __init__(self):
        self.state = "pending"
        self.tick_count = 0

    def tick(self, ctx):
        _ = ctx
        self.tick_count += 1
        self.state = "finished"
        return "finished"


class _HoldStep:
    def __init__(self):
        self.state = "pending"
        self.tick_count = 0

    def tick(self, ctx):
        _ = ctx
        self.tick_count += 1
        self.state = "holding"
        return "holding"


class _SingleStepPlay(BasePlay):
    def __init__(self, step):
        self._step = step
        super().__init__()

    def _create_steps(self):
        return [self._step]


class _FinishPlay(_SingleStepPlay):
    def __init__(self):
        super().__init__(_FinishStep())


class _HoldPlay(_SingleStepPlay):
    def __init__(self):
        super().__init__(_HoldStep())


class _TwoStepPlay(BasePlay):
    def _create_steps(self):
        return [_FinishStep(), _HoldStep()]


def test_play_runner_accepts_first_play_request() -> None:
    runner = PlayRunner()

    result = runner.run(_FinishPlay)

    assert result.accepted is True
    assert result.status == "started"
    assert result.active is True
    assert result.play_class is _FinishPlay
    assert runner.current_play is not None


def test_play_runner_rejects_all_following_requests_while_busy() -> None:
    runner = PlayRunner()
    runner.run(_FinishPlay)

    result = runner.run(_HoldPlay)

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.active is True
    assert result.play_class is _FinishPlay
    assert result.reason == "busy"
    assert isinstance(runner.current_play, _FinishPlay)


def test_play_runner_tick_advances_current_play_and_releases_after_finish() -> None:
    runner = PlayRunner()
    runner.run(_FinishPlay)

    result = runner.tick(_IdleContext())

    assert result.status == "finished"
    assert result.active is False
    assert result.play_class is _FinishPlay
    assert runner.current_play is None


def test_play_runner_returns_idle_when_no_current_play() -> None:
    runner = PlayRunner()

    result = runner.tick(_IdleContext())

    assert result.status == "idle"
    assert result.active is False
    assert result.play_class is None


def test_play_runner_holding_play_keeps_control_and_is_not_released() -> None:
    runner = PlayRunner()
    runner.run(_HoldPlay)

    result = runner.tick(_IdleContext())

    assert result.status == "holding"
    assert result.active is True
    assert result.play_class is _HoldPlay
    assert isinstance(runner.current_play, _HoldPlay)


def test_play_runner_rejects_new_play_after_hold_has_started() -> None:
    runner = PlayRunner()
    runner.run(_HoldPlay)
    runner.tick(_IdleContext())

    result = runner.run(_FinishPlay)

    assert result.accepted is False
    assert result.status == "rejected"
    assert result.active is True
    assert result.play_class is _HoldPlay
    assert result.reason == "busy"


def test_play_logs_state_and_step_transitions(capsys) -> None:
    runner = PlayRunner()
    runner.run(_TwoStepPlay)

    runner.tick(_IdleContext())
    runner.tick(_IdleContext())

    output = capsys.readouterr().out
    assert "play_step: _TwoStepPlay 0->1" in output
    assert "play_state: _TwoStepPlay running" in output
    assert "play_state: _TwoStepPlay holding" in output
