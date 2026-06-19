"""主车回库 Play。"""

from play.base import BasePlay
from play.conditions import yellow_line_ready
from play.steps import AngleStep, HoldVelocityYStep, PositionYStep, VelocityYStep


MASTER_LEAD_DISTANCE = -0.30
RETURN_FORWARD_SPEED = 5
FINAL_FORWARD_SPEED = 3


def _clear_yellow_line_ready(ctx):
    ctx.clear_yellow_line_ready()


def _enter_return_line_wait(ctx):
    ctx.clear_yellow_line_ready()
    ctx.enable_yellow_line_ready_gate()


def _exit_return_line_wait(ctx):
    ctx.disable_yellow_line_ready_gate()


class MasterReturnGaragePlay(BasePlay):
    def _create_steps(self):
        return [
            PositionYStep(MASTER_LEAD_DISTANCE),
            AngleStep(+90),
            VelocityYStep(
                RETURN_FORWARD_SPEED,
                until=yellow_line_ready,
                on_enter=_enter_return_line_wait,
                on_exit=_exit_return_line_wait,
            ),
            AngleStep(-90),
            HoldVelocityYStep(FINAL_FORWARD_SPEED),
        ]
