"""辅车编码器硬件边界.

@file src/assistant/hw/encoders.py
"""

# 这里直接固化当前已确认的编码器板级接线映射。
ENCODER_PINS = {
    "m": ("D15", "D16", True),
    "l": ("C2", "C3", True),
    "r": ("C0", "C1", True),
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
        self._data_ref = None
        self.last_ticks = 0

    def ensure_device(self):
        """按需创建并缓存底层编码器设备.

        @brief 把板级接线映射延迟到真正使用时再绑定到驱动对象。
        """

        if self._device is None:
            from smartcar import encoder

            self._device = encoder(self.phase_a_pin, self.phase_b_pin, self.invert)
            getter = getattr(self._device, "get", None)
            if getter is None:
                raise RuntimeError("编码器硬件接口缺少 get()")
            self._data_ref = getter()
        return self._device

    def read(self):
        """读取当前编码器计数.

        @brief 对底层驱动返回值做非空校验并同步缓存最近一次读数。
        """

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
        """提供与旧接口兼容的单拍读取入口.

        @brief 当前硬件接口没有独立清零语义, 因此直接复用普通读取。
        """

        return self.read()


def build_encoder_bundle():
    """构造辅车编码器边界集合.

    @brief 按当前已确认的板级接线映射构造三路编码器边界。
    @return dict
    """

    bundle = {}
    for name, config in ENCODER_PINS.items():
        bundle[name] = EncoderPort(name, config[0], config[1], config[2])
    return bundle
