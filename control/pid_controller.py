from control.pid_math import clamp


"""PID 控制器模块：提供增量式和位置式 PID 控制器，支持 P/I/D 三项增益。"""


class PIDControllerBase:
    """PID 控制器基类，保存输出限幅和增益参数。"""

    def __init__(self, output_limit=None):
        self.output_limit = output_limit
        self.kp = 0.0
        self.ki = 0.0
        self.kd = 0.0

    def set_gains(self, kp, ki, kd=0.0):
        """设置 PID 增益；兼容旧接口，可省略 `kd`。"""
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def clamp_output(self, value):
        if self.output_limit is None:
            return value
        return clamp(value, -self.output_limit, self.output_limit)


class IncrementalPIDController(PIDControllerBase):
    """增量式 PID 控制器（保存输出的增量更新）。

    使用二阶差分近似实现 D 项增量，适合在累加输出场景下使用。
    """

    def __init__(self, output_limit=None):
        super().__init__(output_limit=output_limit)
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0

    def update(self, target, measurement, dt_s):
        """根据目标值和测量值以及采样间隔更新控制输出并返回当前输出。"""
        if dt_s <= 0:
            dt_s = 1e-6
        err = target - measurement
        # P 项增量
        dp = self.kp * (err - self.prev_error)
        # I 项增量
        di = self.ki * err * dt_s
        # D 项增量
        dd = 0.0
        if self.kd != 0.0:
            dd = self.kd * (err - 2 * self.prev_error + self.prev_prev_error) / dt_s

        du = dp + di + dd
        self.output = self.clamp_output(self.output + du)
        self.prev_prev_error = self.prev_error
        self.prev_error = err
        return self.output

    def reset(self):
        """重置控制器内部状态。"""
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0


class PositionalPIDController(PIDControllerBase):
    """位置式 PID 控制器，输出直接由 P/I/D 求和得到。"""

    def __init__(self, output_limit=None, integral_limit=None):
        super().__init__(output_limit=output_limit)
        self.integral_limit = integral_limit
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, target, measurement, dt_s):
        """根据目标值、测量值和采样间隔计算并返回 P+I+D 输出。"""
        if dt_s <= 0:
            dt_s = 1e-6
        err = target - measurement
        # 积分项
        self.integral += err * dt_s
        if self.integral_limit is not None:
            self.integral = clamp(
                self.integral, -self.integral_limit, self.integral_limit
            )
        # 微分项
        derivative = (err - self.prev_error) / dt_s if dt_s > 0 else 0.0

        output = self.kp * err + self.ki * self.integral + self.kd * derivative
        self.prev_error = err
        return self.clamp_output(output)

    def reset(self):
        """重置位置式控制器的积分及历史误差。"""
        self.integral = 0.0
        self.prev_error = 0.0
