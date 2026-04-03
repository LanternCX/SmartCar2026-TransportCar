"""主车编码器硬件边界.

@file src/master/hw/encoders.py
"""

ENCODER_PINS = {
    "m": ("D15", "D16", True),
    "l": ("C0", "C1", True),
    "r": ("C2", "C3", True),
}


class EncoderPort:
    """编码器端口描述.

    @brief 当前阶段先暴露板级编码器边界对象。
    """

    def __init__(self, name, phase_a_pin, phase_b_pin, invert):
        self.name = str(name)
        self.phase_a_pin = str(phase_a_pin)
        self.phase_b_pin = str(phase_b_pin)
        self.invert = bool(invert)
        self._device = None

    def ensure_device(self):
        if self._device is None:
            from smartcar import encoder

            self._device = encoder(self.phase_a_pin, self.phase_b_pin, self.invert)
        return self._device

    def read(self):
        device = self.ensure_device()
        getter = getattr(device, "get", None)
        if getter is None:
            return 0
        return int(getter())

    def clear(self):
        device = self.ensure_device()
        clearer = getattr(device, "clear", None)
        if clearer is not None:
            clearer()


def build_encoder_bundle():
    """构造主车编码器边界集合.

    @brief 具体引脚映射待统一确认后再写入实现。
    @return dict
    """

    bundle = {}
    for name, config in ENCODER_PINS.items():
        bundle[name] = EncoderPort(name, config[0], config[1], config[2])
    return bundle
