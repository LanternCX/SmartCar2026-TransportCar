"""主车控制基线.

@file src/master/stability/control.py
"""


class HeadingController:
    """最小偏航控制器

    @brief 保留比例控制和角速度限幅语义
    """

    def __init__(self, kp: float = 0.16, omega_limit: float = 15.0) -> None:
        self.kp = float(kp)
        self.omega_limit = float(omega_limit)

    def compute(self, heading_error_deg: float) -> float:
        command = float(heading_error_deg) * self.kp
        if command > self.omega_limit:
            return self.omega_limit
        if command < -self.omega_limit:
            return -self.omega_limit
        return command
