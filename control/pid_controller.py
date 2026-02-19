"""PID 控制器模块.

实现多种 PID 变种,包括增量式 PID、位置式 PID 和带二次项的速度 PID.
"""
from control.pid_math import clamp
from typing import Optional


class PIDControllerBase:
    """PID 控制器基类.
    
    提供共同的参数设置和输出限幅功能.
    """

    def __init__(self, output_limit: Optional[float] = None) -> None:
        """初始化基本 PID 参数.
        
        参数:
            output_limit: 输出限幅值(可选);若为 None,则无限幅.
        """
        self.output_limit = output_limit
        self.kp = 0.0
        self.ki = 0.0
        self.kd = 0.0

    def set_gains(self, kp: float, ki: float = 0.0, kd: float = 0.0) -> None:
        """设置 PID 参数.
        
        参数:
            kp: 比例增益.
            ki: 积分增益.
            kd: 微分增益.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def clamp_output(self, value: float) -> float:
        """对输出进行限幅.
        
        参数:
            value: 待限幅的输出值.
        
        返回:
            限幅后的值.
        """
        if self.output_limit is None:
            return value
        return clamp(value, -self.output_limit, self.output_limit)


class IncrementalPIDController(PIDControllerBase):
    """增量式 PID 控制器.
    
    输出增量:du = kp*(e - e_prev) + ki*e*dt + kd*(e - 2*e_prev + e_prev_prev) / dt
    """

    def __init__(self, output_limit: Optional[float] = None) -> None:
        """初始化增量式 PID 控制器.
        
        参数:
            output_limit: 输出限幅值(可选).
        """
        super().__init__(output_limit=output_limit)
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0

    def update(self, target: float, now: float, dt_s: float = 1.0) -> float:
        """计算 PID 输出.
        
        参数:
            target: 目标值.
            now: 当前值.
            dt_s: 时间增量(秒).
        
        返回:
            PID 输出(已限幅).
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

    def reset(self) -> None:
        """重置控制器内部状态."""
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0


class PositionalPIDController(PIDControllerBase):
    """位置式 PID 控制器.
    
    输出:u = kp*e + ki*integral(e) + kd*de/dt
    """

    def __init__(self, output_limit: Optional[float] = None, integral_limit: Optional[float] = None) -> None:
        """初始化位置式 PID 控制器.
        
        参数:
            output_limit: 输出限幅值(可选).
            integral_limit: 积分项的上限值(可选).
        """
        super().__init__(output_limit=output_limit)
        self.integral = 0.0
        self.prev_error = 0.0
        self.integral_limit = integral_limit

    def update(self, target: float, now: float, dt_s: float = 1.0) -> float:
        """计算 PID 输出.
        
        参数:
            target: 目标值.
            now: 当前值.
            dt_s: 时间增量(秒).
        
        返回:
            PID 输出(已限幅).
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

    def reset(self) -> None:
        """重置控制器内部状态."""
        self.integral = 0.0
        self.prev_error = 0.0


class SpeedPIDController(PIDControllerBase):
    """带有二次项和前馈的增量式 PI 控制器.
    
    用于速度环,支持从系统辨识参数(增益、时间常数)进行前馈补偿.
    输出:u_feedback = u_inc(增量式 PI)+ u_ff(前馈)
    """

    def __init__(self, output_limit: Optional[float] = None, ki2: float = 0.0, plant_gain: Optional[float] = None, plant_tau: Optional[float] = None) -> None:
        """初始化速度 PID 控制器.
        
        参数:
            output_limit: 输出限幅值(可选).
            ki2: 二次积分增益.
            plant_gain: 系统增益(速度/占空比).
            plant_tau: 系统时间常数.
        """
        super().__init__(output_limit=output_limit)
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0
        self.ki2 = ki2
        self.plant_gain = plant_gain
        self.plant_tau = plant_tau

    def set_gains(self, kp: float, ki: float, ki2: float = 0.0) -> None:
        """设置 PID 参数.
        
        参数:
            kp: 比例增益.
            ki: 积分增益.
            ki2: 二次积分增益.
        """
        super().set_gains(kp, ki)
        self.ki2 = ki2

    def set_plant(self, gain: Optional[float] = None, tau: Optional[float] = None) -> None:
        """设置系统辨识参数.
        
        参数:
            gain: 系统增益.
            tau: 系统时间常数.
        """
        self.plant_gain = gain
        self.plant_tau = tau

    def _feedforward(self, target: float, dt_s: float) -> float:
        """计算前馈项.
        
        使用一阶系统模型进行前馈:u_ff = (r/g) + (tau/g)*(dr/dt)
        
        参数:
            target: 目标速度.
            dt_s: 时间增量.
        
        返回:
            前馈补偿值.
        """
        if self.plant_gain is None or self.plant_gain <= 0:
            return 0.0
        dr_dt = (target - self.prev_target) / dt_s if dt_s > 0 else 0.0
        tau_term = (self.plant_tau or 0.0) * dr_dt
        u_ff = (target + tau_term) / self.plant_gain
        return u_ff

    def update(self, target: float, now: float, dt_s: float = 1.0) -> float:
        """计算 PID 输出.
        
        参数:
            target: 目标值.
            now: 当前值.
            dt_s: 时间增量(秒).
        
        返回:
            PID 输出(已限幅).
        """
        if dt_s <= 0:
            dt_s = 1
        err = target - now
        # P 项增量
        dp = self.kp * (err - self.prev_error)
        # I 项增量
        di = self.ki * err * dt_s
        # 二次项 I2 增量
        i2 = self.ki2 * (err * abs(err))

        du_fb = dp + di + i2
        self.output = self.clamp_output(self.output + du_fb)

        u_ff = self._feedforward(target, dt_s)
        total = self.clamp_output(self.output + u_ff)

        self.prev_error = err
        self.prev_target = target
        return total

    def reset(self) -> None:
        """重置控制器内部状态."""
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0
