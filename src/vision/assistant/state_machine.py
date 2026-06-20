"""辅车子状态机

@file src/vision/assistant/state_machine.py
"""

from utils.startup_log import log

# 辅车子状态编号
ASSISTANT_STATE_IDLE = 0
ASSISTANT_STATE_FOLLOW = 1
ASSISTANT_STATE_APPROACH_OBJECT = 2
ASSISTANT_STATE_ORBIT = 3
ASSISTANT_STATE_TRANSPORT_OBJECT = 4
ASSISTANT_STATE_CLEAR_OBJECT = 5
ASSISTANT_STATE_RETURN_FOLLOW = 6
ASSISTANT_STATE_FINISHED = 7
_STATE_NAMES = (
    "IDLE",
    "FOLLOW",
    "APPROACH_OBJECT",
    "ORBIT",
    "TRANSPORT_OBJECT",
    "CLEAR_OBJECT",
    "RETURN_FOLLOW",
    "FINISHED",
)

# 辅车目标编号
ASSISTANT_TARGET_NONE = 0
ASSISTANT_TARGET_OBJECT = 1

# 辅车视觉事件编号
class AssistantStateMachine:
    """维护辅车由主车驱动的子状态"""

    def __init__(self):
        self.state = ASSISTANT_STATE_FOLLOW
        self.target = ASSISTANT_TARGET_NONE
        self.arg = 0

    def _enter_state(self, state):
        """进入辅车子状态并输出一次跳转日志"""

        state = int(state)
        if self.state == state:
            return
        self.state = state
        log("assistant_state", _STATE_NAMES[state])

    def apply_master_state(self, state, target, arg):
        """应用主车下发的辅车子状态

        @param state 辅车子状态编号
        @param target 辅车目标编号
        @param arg 辅车状态短参数
        @return 状态是否被接受
        """

        state = int(state)
        target = int(target)
        if (
            state != ASSISTANT_STATE_IDLE
            and state != ASSISTANT_STATE_FOLLOW
            and state != ASSISTANT_STATE_APPROACH_OBJECT
            and state != ASSISTANT_STATE_ORBIT
            and state != ASSISTANT_STATE_TRANSPORT_OBJECT
            and state != ASSISTANT_STATE_CLEAR_OBJECT
            and state != ASSISTANT_STATE_RETURN_FOLLOW
            and state != ASSISTANT_STATE_FINISHED
        ):
            return False
        if (
            (state == ASSISTANT_STATE_RETURN_FOLLOW or state == ASSISTANT_STATE_FINISHED)
            and target != ASSISTANT_TARGET_NONE
        ):
            return False
        if (
            (
                state == ASSISTANT_STATE_APPROACH_OBJECT
                or state == ASSISTANT_STATE_ORBIT
                or state == ASSISTANT_STATE_TRANSPORT_OBJECT
                or state == ASSISTANT_STATE_CLEAR_OBJECT
            )
            and target != ASSISTANT_TARGET_OBJECT
        ):
            return False
        self._enter_state(state)
        self.target = target
        self.arg = int(arg)
        return True

    def handle_event(self, event, value):
        """消费辅车本地视觉事件"""

        _ = value
        event = int(event)
        if self.state == ASSISTANT_STATE_RETURN_FOLLOW:
            return

    def is_idle(self):
        """判断辅车是否处于 idle 子状态"""

        return self.state == ASSISTANT_STATE_IDLE

    def is_finished(self):
        """判断辅车是否处于完成停止态"""

        return self.state == ASSISTANT_STATE_FINISHED
