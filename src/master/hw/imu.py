"""主车 IMU 硬件边界.

@file src/master/hw/imu.py
"""


class ImuPort:
    """IMU 边界对象.

    @brief 当前阶段先暴露原始读数与零漂入口占位。
    """

    def __init__(self):
        self.offsets = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._device = None
        self._data_ref = None
        self.last_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.last_calibrated = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def ensure_device(self):
        if self._device is None:
            from seekfree import IMU660RX

            self._device = IMU660RX()
            getter = getattr(self._device, "get", None)
            if getter is None:
                raise RuntimeError("IMU 硬件接口缺少 get()")
            self._data_ref = getter()
        return self._device

    def read_raw(self):
        self.ensure_device()
        raw = self._data_ref
        if raw is None:
            raise RuntimeError("IMU 硬件接口返回空读数")
        values = tuple(raw)
        if len(values) != 6:
            raise RuntimeError("IMU 硬件接口返回的轴数量不正确")
        self.last_raw = tuple(float(value) for value in values)
        return self.last_raw

    def read_calibrated(self):
        raw = self.read_raw()
        calibrated = []
        for index, value in enumerate(raw):
            calibrated.append(float(value) - float(self.offsets[index]))
        self.last_calibrated = tuple(calibrated)
        return self.last_calibrated

    def apply_offsets(self, offsets):
        prepared = [0.0] * 6
        for index, value in enumerate(tuple(offsets)[:6]):
            prepared[index] = float(value)
        self.offsets = tuple(prepared)


def build_imu_bundle():
    """构造主车 IMU 边界对象.

    @brief IMU 型号已确认，具体读写接线在后续硬件联调中补齐。
    @return ImuPort
    """

    return ImuPort()
