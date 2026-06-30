"""辅车回库 Play。"""

from play.base import BasePlay
from play.steps import AngleStep, PositionYStep, VelocityYStep


ASSISTANT_LEAD_DISTANCE = 0.70
RETURN_FORWARD_SPEED = 3
FINAL_FORWARD_SPEED = 8
RETURN_POSITION_SPEED = 5


def _clear_yellow_line_ready(ctx):
    ctx.clear_yellow_line_ready()


def _yellow_line_ready(ctx):
    return ctx.yellow_line_ready()


def _enter_return_line_wait(ctx):
    ctx.clear_yellow_line_ready()
    ctx.enable_yellow_line_ready_gate()


def _exit_return_line_wait(ctx):
    ctx.disable_yellow_line_ready_gate()


class AssistantReturnGaragePlay(BasePlay):
    def _create_steps(self):
        return [
            PositionYStep(ASSISTANT_LEAD_DISTANCE, max_speed_cmd=RETURN_POSITION_SPEED),
            AngleStep(-90),
            VelocityYStep(
                RETURN_FORWARD_SPEED,
                until=_yellow_line_ready,
                on_enter=_enter_return_line_wait,
                on_exit=_exit_return_line_wait,
            ),
            AngleStep(-90),
            VelocityYStep(FINAL_FORWARD_SPEED),
        ]
