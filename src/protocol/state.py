"""状态、目标与事件编号常量

@file src/protocol/state.py
"""

# 主车单车状态编号
STATE_IDLE = 0
STATE_SEARCH_OBJECT = 1
STATE_ORBITING = 2
STATE_STOP = 3

# 目标编号
TARGET_NONE = 0
TARGET_OBJECT = 1

# 事件编号
EVENT_TARGET_FOUND = 6
