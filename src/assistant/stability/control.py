"""辅车最小控制语义

@file src/assistant/stability/control.py
"""


class HeadingController:
    """最小偏航保持控制器

    @brief 保留角度误差直接映射角速度命令的最小语义
    """

    def __init__(self, kp: float = 0.16, omega_limit: float = 15.0) -> None:
        self.kp = float(kp)
        self.omega_limit = abs(float(omega_limit))

    def compute(self, heading_error_deg: float) -> float:
        """计算角速度输出

        @brief 对偏航误差做比例控制并限幅
        @param heading_error_deg 偏航误差, 单位度
        @return float
        """

        output = float(heading_error_deg) * self.kp
        if output > self.omega_limit:
            return self.omega_limit
        if output < -self.omega_limit:
            return -self.omega_limit
        return output
