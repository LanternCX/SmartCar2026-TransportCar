"""Play 播放器。"""

from play.base import PlayRunResult


class PlayRunner:
    """单 Play 播放器."""

    def __init__(self):
        self.current_play = None

    def run(self, play_class):
        if self.current_play is not None:
            return PlayRunResult(
                accepted=False,
                status="rejected",
                active=True,
                play_class=self.current_play.__class__,
                reason="busy",
            )
        self.current_play = play_class()
        return PlayRunResult(
            accepted=True,
            status="started",
            active=True,
            play_class=play_class,
        )

    def tick(self, ctx):
        if self.current_play is None:
            return PlayRunResult(
                accepted=False,
                status="idle",
                active=False,
                play_class=None,
            )
        result = self.current_play.tick(ctx)
        if result.status == "finished":
            self.current_play = None
        return result
