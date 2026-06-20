"""Play 基础对象。"""

from utils.startup_log import log


PLAY_STATE_IDLE = "idle"
PLAY_STATE_RUNNING = "running"
PLAY_STATE_HOLDING = "holding"
PLAY_STATE_FINISHED = "finished"
PLAY_STATE_FAILED = "failed"


class PlayRunResult:
    """描述单次 run 或 tick 的结果."""

    def __init__(
        self,
        accepted,
        status,
        active,
        play_class=None,
        reason=None,
    ):
        self.accepted = bool(accepted)
        self.status = str(status)
        self.active = bool(active)
        self.play_class = play_class
        self.reason = reason


class BasePlay:
    """固定步骤序列的最小 Play 基类."""

    def __init__(self):
        self.state = PLAY_STATE_IDLE
        self.step_index = 0
        self.last_result = PlayRunResult(
            accepted=True,
            status=PLAY_STATE_IDLE,
            active=False,
            play_class=self.__class__,
        )
        self._steps = list(self._create_steps())

    def _create_steps(self):
        raise NotImplementedError

    def _set_state(self, state):
        state = str(state)
        if self.state == state:
            return
        self.state = state
        log("play_state", "%s %s" % (self.__class__.__name__, state))

    def _set_step_index(self, step_index):
        step_index = int(step_index)
        if self.step_index == step_index:
            return
        previous = int(self.step_index)
        self.step_index = step_index
        log(
            "play_step",
            "%s %d->%d" % (self.__class__.__name__, previous, step_index),
        )

    def tick(self, ctx):
        if self.step_index >= len(self._steps):
            self._set_state(PLAY_STATE_FINISHED)
            self.last_result = PlayRunResult(
                accepted=True,
                status=PLAY_STATE_FINISHED,
                active=False,
                play_class=self.__class__,
            )
            return self.last_result

        current = self._steps[self.step_index]
        step_status = current.tick(ctx)
        if step_status == "finished":
            self._set_step_index(self.step_index + 1)
            if self.step_index >= len(self._steps):
                self._set_state(PLAY_STATE_FINISHED)
                self.last_result = PlayRunResult(
                    accepted=True,
                    status=PLAY_STATE_FINISHED,
                    active=False,
                    play_class=self.__class__,
                )
                return self.last_result
            self._set_state(PLAY_STATE_RUNNING)
            self.last_result = PlayRunResult(
                accepted=True,
                status=PLAY_STATE_RUNNING,
                active=True,
                play_class=self.__class__,
            )
            return self.last_result
        if step_status == "holding":
            self._set_state(PLAY_STATE_HOLDING)
            self.last_result = PlayRunResult(
                accepted=True,
                status=PLAY_STATE_HOLDING,
                active=True,
                play_class=self.__class__,
            )
            return self.last_result
        self._set_state(PLAY_STATE_RUNNING)
        self.last_result = PlayRunResult(
            accepted=True,
            status=PLAY_STATE_RUNNING,
            active=True,
            play_class=self.__class__,
        )
        return self.last_result
