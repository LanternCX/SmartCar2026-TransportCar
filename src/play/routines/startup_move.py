"""启动动作 Play。"""

from play.base import BasePlay
from play.steps import AngleStep, PositionYStep


STARTUP_FIRST_FORWARD_DISTANCE = 0.70
STARTUP_RIGHT_TURN_DEG = 90.0
STARTUP_SECOND_FORWARD_DISTANCE = 1.10
STARTUP_LEFT_TURN_DEG = -90.0
STARTUP_MOVE_SPEED = 5.0


class StartupMovePlay(BasePlay):
    def _create_steps(self):
        return [
            PositionYStep(STARTUP_FIRST_FORWARD_DISTANCE, max_speed_cmd=STARTUP_MOVE_SPEED),
            AngleStep(STARTUP_RIGHT_TURN_DEG),
            PositionYStep(STARTUP_SECOND_FORWARD_DISTANCE, max_speed_cmd=STARTUP_MOVE_SPEED),
            AngleStep(STARTUP_LEFT_TURN_DEG),
        ]
