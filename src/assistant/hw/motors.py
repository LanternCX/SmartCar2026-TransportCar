"""辅车电机硬件边界.

@file src/assistant/hw/motors.py
"""

MOTOR_PORTS = {
    "m": ("PWM_C30_DIR_C31", False),
    "l": ("PWM_D6_DIR_D7", True),
    "r": ("PWM_D4_DIR_D5", False),
}


class MotorPort:
    """电机端口描述.

    @brief 当前阶段先暴露板级电机边界对象。
    """

    def __init__(self, name, port_name, invert):
        self.name = str(name)
        self.port_name = str(port_name)
        self.invert = bool(invert)
        self.frequency_hz = 13000
        self._device = None

    def ensure_device(self):
        if self._device is None:
            from seekfree import MOTOR_CONTROLLER

            port = getattr(MOTOR_CONTROLLER, self.port_name)
            self._device = MOTOR_CONTROLLER(
                port,
                self.frequency_hz,
                duty=0,
                invert=self.invert,
            )
        return self._device

    def set_duty(self, duty):
        device = self.ensure_device()
        device.duty(int(duty))

    def stop(self):
        self.set_duty(0)


def build_motor_bundle():
    """构造辅车电机边界集合.

    @brief 具体引脚映射待统一确认后再写入实现。
    @return dict
    """

    bundle = {}
    for name, config in MOTOR_PORTS.items():
        bundle[name] = MotorPort(name, config[0], config[1])
    return bundle
