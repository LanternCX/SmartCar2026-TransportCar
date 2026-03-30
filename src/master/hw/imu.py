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

    def ensure_device(self):
        if self._device is None:
            from seekfree import IMU660RX

            self._device = IMU660RX()
        return self._device

    def read_raw(self):
        device = self.ensure_device()
        getter = getattr(device, "get", None)
        if getter is None:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return tuple(getter())

    def apply_offsets(self, offsets):
        self.offsets = tuple(offsets)


def build_imu_bundle():
    """构造主车 IMU 边界对象.

    @brief IMU 型号已确认，具体读写接线在后续硬件联调中补齐。
    @return ImuPort
    """

    return ImuPort()
