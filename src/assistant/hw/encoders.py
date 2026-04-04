"""辅车编码器硬件边界.

@file src/assistant/hw/encoders.py
"""

# legacy 与当前主线共用同一套编码器接线, 这里直接固化确认后的板级映射。
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
        self.last_ticks = 0

    def ensure_device(self):
        if self._device is None:
            from smartcar import encoder

            self._device = encoder(self.phase_a_pin, self.phase_b_pin, self.invert)
        return self._device

    def read(self):
        device = self.ensure_device()
        getter = getattr(device, "get", None)
        if getter is None:
            raise RuntimeError("编码器硬件接口缺少 get()")
        ticks = getter()
        if ticks is None:
            raise RuntimeError("编码器硬件接口返回空读数")
        self.last_ticks = int(ticks)
        return self.last_ticks

    def read_and_clear(self):
        return self.read()


def build_encoder_bundle():
    """构造辅车编码器边界集合.

    @brief 按 legacy 已确认映射构造三路编码器边界。
    @return dict
    """

    bundle = {}
    for name, config in ENCODER_PINS.items():
        bundle[name] = EncoderPort(name, config[0], config[1], config[2])
    return bundle
