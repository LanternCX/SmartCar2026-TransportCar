from control.pid_math import clamp


"""PID 控制器模块"""


class PIDControllerBase:
    """PID 控制器基类"""

    def __init__(self, output_limit=None):
        self.output_limit = output_limit
        self.kp = 0.0
        self.ki = 0.0
        self.kd = 0.0

    def set_gains(self, kp, ki=0.0, kd=0.0):
        """`
        设置 PID 参数，可选微分项。
        :param kp: 比例增益
        :param ki: 积分增益
        :param kd: 微分增益
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def clamp_output(self, value):
        if self.output_limit is None:
            return value
        return clamp(value, -self.output_limit, self.output_limit)


class IncrementalPIDController(PIDControllerBase):
    """增量式 PID 控制器"""

    def __init__(self, output_limit=None):
        super().__init__(output_limit=output_limit)
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0

    def update(self, target, now, dt_s=1.0):
        """
        计算 PID 输出
        :param target: 目标值
        :param now: 当前值
        :param dt_s: 时间增量
        """
        if dt_s <= 0:
            dt_s = 1
        err = target - now
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
        """重置控制器内部状态"""
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0


class PositionalPIDController(PIDControllerBase):
    """位置式 PID 控制器"""

    def __init__(self, output_limit=None):
        super().__init__(output_limit=output_limit)
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, target, now, dt_s=1.0):
        """
        计算 PID 输出
        :param target: 目标值
        :param now: 当前值
        :param dt_s: 时间增量
        """
        if dt_s <= 0:
            dt_s = 1
        err = target - now
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
        """重置控制器内部状态"""
        self.integral = 0.0
        self.prev_error = 0.0


class SpeedPIDController(PIDControllerBase):
    """带有二次项的增量式 PI 控制器"""

    def __init__(self, output_limit=None, ki2=0.0):
        super().__init__(output_limit=output_limit)
        self.output = 0.0
        self.prev_error = 0.0
        self.ki2 = ki2

    def set_gains(self, kp, ki, ki2=0.0):
        """
        设置 PID 参数
        :param kp: 比例增益
        :param ki: 积分增益
        :param ki2: 二次积分增益
        """
        super().set_gains(kp, ki)
        self.ki2 = ki2

    def update(self, target, now, dt_s=1.0):
        """
        计算 PID 输出
        :param target: 目标值
        :param now: 当前值
        :param dt_s: 时间增量
        """
        if dt_s <= 0:
            dt_s = 1
        err = target - now
        # P 项增量
        dp = self.kp * (err - self.prev_error)
        # I 项增量
        di = self.ki * err * dt_s
        # 二次项 I2 增量
        i2 = self.ki2 * (err * err)

        du = dp + di + i2
        self.output = self.clamp_output(self.output + du)
        self.prev_error = err
        return self.output

    def reset(self):
        """重置控制器内部状态"""
        self.output = 0.0
        self.prev_error = 0.0
