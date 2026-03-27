"""辅车控制辅助计算

@file src/assistant/stability/control.py
"""


class HeadingController:
    """根据偏航误差生成角速度命令

    @brief 提供比例控制和角速度限幅
    """

    def __init__(self, kp=0.16, omega_limit=15.0):
        # 比例系数和输出限幅在控制器内统一收口
        self.kp = float(kp)
        self.omega_limit = abs(float(omega_limit))

    def compute(self, heading_error_deg):
        """计算角速度输出

        @brief 按比例系数换算并限制输出范围
        @param heading_error_deg 偏航误差, 单位度
        @return float
        """

        output = float(heading_error_deg) * self.kp
        if output > self.omega_limit:
            return self.omega_limit
        if output < -self.omega_limit:
            return -self.omega_limit
        return output
