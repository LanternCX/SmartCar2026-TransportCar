"""主车 PID 边界.

@file src/master/ctrl/pid.py
"""


def _clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


class PidController:
    def __init__(self):
        self.last_output = 0.0


class SpeedController:
    """封装单轮速度环与前馈补偿."""

    def __init__(self, output_limit, plant_gain=None, plant_tau=None):
        self.output_limit = float(output_limit)
        self.plant_gain = plant_gain
        self.plant_tau = plant_tau
        self.kp = 0.0
        self.ki = 0.0
        self.ki2 = 0.0
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0

    def set_gains(self, kp, ki, ki2=0.0):
        """写入单轮速度环使用的增益参数.

        @brief 允许在装配阶段统一下发参数, 运行拍内不再重复改写。
        """

        self.kp = float(kp)
        self.ki = float(ki)
        self.ki2 = float(ki2)

    def _feedforward(self, target, dt_s):
        if self.plant_gain is None or float(self.plant_gain) <= 0.0:
            return 0.0
        if dt_s <= 0.0:
            dt_s = 1.0
        dr_dt = (float(target) - self.prev_target) / float(dt_s)
        tau_term = (float(self.plant_tau or 0.0)) * dr_dt
        return (float(target) + tau_term) / float(self.plant_gain)

    def update(self, target, now, dt_s):
        """根据目标速度和当前反馈计算本拍电机输出.

        @brief 这里把增量式 PID 和辨识前馈合并, 返回最终给电机层的占空比命令。
        """

        if dt_s <= 0.0:
            dt_s = 1.0
        err = float(target) - float(now)
        dp = self.kp * (err - self.prev_error)
        di = self.ki * err * float(dt_s)
        i2 = self.ki2 * (err * abs(err))
        self.output = _clamp(
            self.output + dp + di + i2,
            -self.output_limit,
            self.output_limit,
        )
        total = _clamp(
            self.output + self._feedforward(target, dt_s),
            -self.output_limit,
            self.output_limit,
        )
        self.prev_error = err
        self.prev_target = float(target)
        return total

    def reset(self):
        """清空跨周期误差和输出状态.

        @brief 在停机或模式切换时调用, 避免旧积分残留带入下一段动作。
        """

        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0


def build_wheel_speed_controllers(pid_map, ident_lookup, output_limit):
    """按轮位装配速度环控制器集合.

    @brief 同时把 PID 参数和辨识前馈参数绑定到每一路控制器, 供运行时直接复用。
    """

    wheel_controllers = {}
    for name in ("m", "l", "r"):
        gains = pid_map.get(name, (0.0, 0.0, 0.0))
        plant_gain, plant_tau = ident_lookup.get(name, (None, None))
        controller = SpeedController(
            output_limit=output_limit,
            plant_gain=plant_gain,
            plant_tau=plant_tau,
        )
        controller.set_gains(gains[0], gains[1], gains[2])
        wheel_controllers[name] = controller
    return wheel_controllers


def apply_wheel_speed_control(state, wheel_targets, limit, motors=None):
    """把车体目标轮速落实成每个轮位的输出命令.

    @brief 这个入口负责限幅、更新状态快照并在提供电机对象时直接下发占空比。
    """

    dt_s = float(getattr(state, "tick_s", 0.0) or 0.0)
    if dt_s <= 0.0:
        tick_ms = float(getattr(state, "tick_ms", 0.0) or 0.0)
        dt_s = tick_ms / 1000.0 if tick_ms > 0.0 else 0.0

    outputs = {}
    for name in ("m", "l", "r"):
        raw = _clamp(float(wheel_targets.get(name, 0.0)), -float(limit), float(limit))
        state.target_wheel_speeds[name] = raw
        duty = state.wheel_controllers[name].update(
            raw,
            state.wheel_speeds.get(name, 0.0),
            dt_s,
        )
        outputs[name] = duty
        state.motor_duties[name] = int(duty)
        if motors is None:
            continue
        motor = motors.get(name)
        if motor is not None:
            motor.set_duty(int(duty))
    return outputs
