"""主车决策结果生成

@file src/master/decision.py
"""

from master.vision.decision import Decision, decide_from_observation, decide_from_state


__all__ = ["Decision", "decide_from_state", "decide_from_observation"]
