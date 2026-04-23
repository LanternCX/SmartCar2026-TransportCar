"""@file pid_controller.py
@brief PID 控制器模块

实现多种 PID 变种, 包括增量式 PID、位置式 PID 和带二次项的速度 PID,
支持限幅、前馈补偿和参数辨识
"""
from control.pid_math import clamp


class PIDControllerBase:
    """@class PIDControllerBase
    @brief PID 控制器基类

    提供共同的参数设置和输出限幅功能, 各子类可根据需要扩展
    """

    def __init__(self, output_limit=None):
        """@brief 初始化基本 PID 参数

        @param output_limit 输出限幅值, 单位同输出信号; 若为 None 则无限幅
        """
        self.output_limit = output_limit
        self.kp = 0.0
        self.ki = 0.0
        self.kd = 0.0

    def set_gains(self, kp, ki=0.0, kd=0.0):
        """@brief 设置 PID 参数

        @param kp 比例增益, 响应偏差的强度
        @param ki 积分增益, 消除稳态误差的系数
        @param kd 微分增益, 阻尼项以减少振荡
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def clamp_output(self, value):
        """@brief 对输出进行限幅

        防止控制输出超过硬件允许范围, 保护执行机构

        @param value 待限幅的输出值
        @return 限幅后的值, 范围为 [-output_limit, output_limit]
        """
        if self.output_limit is None:
            return value
        return clamp(value, -self.output_limit, self.output_limit)


class IncrementalPIDController(PIDControllerBase):
    """@class IncrementalPIDController
    @brief 增量式 PID 控制器

    输出增量式控制, du = kp*(e - e_prev) + ki*e*dt + kd*(e - 2*e_prev + e_prev_prev) / dt
    适合于执行机构本身可以接受增量命令的场景(如转速调节)
    """

    def __init__(self, output_limit=None):
        """@brief 初始化增量式 PID 控制器

        内部维护上一周期和上上一周期的误差, 以及累积输出

        @param output_limit 输出限幅值(可选)
        """
        super().__init__(output_limit=output_limit)
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0

    def update(self, target, now, dt_s=1.0):
        """@brief 计算 PID 输出

        @param target 目标值
        @param now 当前值
        @param dt_s 时间增量(秒), 用于积分和微分项的时间补偿
        @return PID 输出(已限幅)
        """
        if dt_s <= 0:
            dt_s = 1
        err = target - now
        dp = self.kp * (err - self.prev_error)
        di = self.ki * err * dt_s
        dd = 0.0
        if self.kd != 0.0:
            dd = self.kd * (err - 2 * self.prev_error + self.prev_prev_error) / dt_s

        du = dp + di + dd
        self.output = self.clamp_output(self.output + du)
        self.prev_prev_error = self.prev_error
        self.prev_error = err
        return self.output

    def reset(self):
        """@brief 重置控制器内部状态

        清空累积输出和误差历史, 用于切换控制模式或重新初始化
        """
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_prev_error = 0.0


class PositionalPIDController(PIDControllerBase):
    """@class PositionalPIDController
    @brief 位置式 PID 控制器

    输出位置式控制, u = kp*e + ki*integral(e) + kd*de/dt
    输出为绝对位置或状态, 不是增量, 适合于直接控制目标量的场景
    """

    def __init__(self, output_limit=None, integral_limit=None):
        """@brief 初始化位置式 PID 控制器

        @param output_limit 输出限幅值(可选)
        @param integral_limit 积分项的上限值(可选); 若设置, 则积分项不会超过此界, 避免积分饱和
        """
        super().__init__(output_limit=output_limit)
        self.integral = 0.0
        self.prev_error = 0.0
        self.integral_limit = integral_limit

    def update(self, target, now, dt_s=1.0):
        """@brief 计算 PID 输出

        @param target 目标值
        @param now 当前值
        @param dt_s 时间增量(秒)
        @return PID 输出(已限幅)
        """
        if dt_s <= 0:
            dt_s = 1
        err = target - now
        self.integral += err * dt_s
        if self.integral_limit is not None:
            self.integral = clamp(
                self.integral, -self.integral_limit, self.integral_limit
            )
        derivative = (err - self.prev_error) / dt_s if dt_s > 0 else 0.0

        output = self.kp * err + self.ki * self.integral + self.kd * derivative
        self.prev_error = err
        return self.clamp_output(output)

    def reset(self):
        """@brief 重置控制器内部状态

        清空积分项和误差历史
        """
        self.integral = 0.0
        self.prev_error = 0.0


class SpeedPIDController(PIDControllerBase):
    """@class SpeedPIDController
    @brief 带有二次项和前馈的增量式 PI 控制器

    用于速度环, 支持从系统辨识参数(增益、时间常数)进行前馈补偿
    输出: u_feedback = u_inc(增量式 PI) + u_ff(前馈)
    """

    def __init__(self, output_limit=None, ki2=0.0, plant_gain=None, plant_tau=None):
        """@brief 初始化速度 PID 控制器

        @param output_limit 输出限幅值(可选)
        @param ki2 二次积分增益, 用于加速偏差项 (err*|err|) 的反馈
        @param plant_gain 系统增益(速度/占空比), 来自系统辨识
        @param plant_tau 系统时间常数(秒), 来自系统辨识
        """
        super().__init__(output_limit=output_limit)
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0
        self.ki2 = ki2
        self.plant_gain = plant_gain
        self.plant_tau = plant_tau

    def set_gains(self, kp, ki, ki2=0.0):
        """@brief 设置 PID 参数

        @param kp 比例增益
        @param ki 积分增益
        @param ki2 二次积分增益
        """
        super().set_gains(kp, ki)
        self.ki2 = ki2

    def set_plant(self, gain=None, tau=None):
        """@brief 设置系统辨识参数

        这些参数用于前馈项的计算, 提高对目标变化的响应速度

        @param gain 系统增益(速度/占空比)
        @param tau 系统时间常数(秒)
        """
        self.plant_gain = gain
        self.plant_tau = tau

    def _feedforward(self, target, dt_s):
        """@brief 计算前馈项

        使用一阶系统模型进行前馈补偿: u_ff = (r/g) + (tau/g)*(dr/dt),
        其中 r 是目标速度, g 是增益, tau 是时间常数

        @param target 目标速度
        @param dt_s 时间增量(秒)
        @return 前馈补偿值
        """
        if self.plant_gain is None or self.plant_gain <= 0:
            return 0.0
        dr_dt = (target - self.prev_target) / dt_s if dt_s > 0 else 0.0
        tau_term = (self.plant_tau or 0.0) * dr_dt
        u_ff = (target + tau_term) / self.plant_gain
        return u_ff

    def update(self, target, now, dt_s=1.0):
        """@brief 计算 PID 输出

        反馈为增量式 PI + 二次项, 再加上前馈项

        @param target 目标值
        @param now 当前值
        @param dt_s 时间增量(秒)
        @return PID 输出(已限幅)
        """
        if dt_s <= 0:
            dt_s = 1
        err = target - now
        dp = self.kp * (err - self.prev_error)
        di = self.ki * err * dt_s
        i2 = self.ki2 * (err * abs(err))

        du_fb = dp + di + i2
        self.output = self.clamp_output(self.output + du_fb)

        u_ff = self._feedforward(target, dt_s)
        total = self.clamp_output(self.output + u_ff)

        self.prev_error = err
        self.prev_target = target
        return total

    def reset(self):
        """@brief 重置控制器内部状态

        清空反馈输出和误差历史, 保留前馈参数
        """
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0
