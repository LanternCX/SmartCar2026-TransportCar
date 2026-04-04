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
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0


def build_wheel_speed_controllers(pid_map, ident_lookup, output_limit):
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
    outputs = {}
    for name in ("m", "l", "r"):
        raw = _clamp(float(wheel_targets.get(name, 0.0)), -float(limit), float(limit))
        state.target_wheel_speeds[name] = raw
        duty = state.wheel_controllers[name].update(
            raw,
            state.wheel_speeds.get(name, 0.0),
            state.tick_s,
        )
        outputs[name] = duty
        state.motor_duties[name] = int(duty)
        if motors is None:
            continue
        motor = motors.get(name)
        if motor is not None:
            motor.set_duty(int(duty))
    return outputs
