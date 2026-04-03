"""辅车 PID 边界.

@file src/assistant/ctrl/pid.py
"""


class PidController:
    def __init__(self):
        self.last_output = 0.0
