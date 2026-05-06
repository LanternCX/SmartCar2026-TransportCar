"""辅车子状态机

@file src/vision/assistant/state_machine.py
"""

# 辅车子状态编号
ASSISTANT_STATE_IDLE = 0
ASSISTANT_STATE_FOLLOW = 1
ASSISTANT_STATE_APPROACH_OBJECT = 2
ASSISTANT_STATE_ORBIT = 3
ASSISTANT_STATE_TRANSPORT_OBJECT = 4
ASSISTANT_STATE_CLEAR_OBJECT = 5

# 辅车目标编号
ASSISTANT_TARGET_NONE = 0
ASSISTANT_TARGET_OBJECT = 1


class AssistantStateMachine:
    """维护辅车由主车驱动的子状态"""

    def __init__(self):
        self.state = ASSISTANT_STATE_FOLLOW
        self.target = ASSISTANT_TARGET_NONE
        self.arg = 0

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
        self.state = state
        self.target = target
        self.arg = int(arg)
        return True

    def is_idle(self):
        """判断辅车是否处于 idle 子状态"""

        return self.state == ASSISTANT_STATE_IDLE
