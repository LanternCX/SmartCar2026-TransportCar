"""主车滤波基线.

@file src/master/stability/filtering.py
"""


class SpikeMedianFilter:
    """尖峰抑制滤波器

    @brief 使用滑动窗口中值抑制单点异常值
    """

    def __init__(self, window=5):
        self.window = max(1, int(window))
        self._values = []

    def update(self, value):
        self._values.append(float(value))
        if len(self._values) > self.window:
            del self._values[0]
        ordered = sorted(self._values)
        return float(ordered[len(ordered) // 2])


class DiffLimitFilter:
    """差值限幅滤波器

    @brief 限制连续输出之间的最大跳变
    """

    def __init__(self, max_delta=5.0):
        self.max_delta = float(max_delta)
        self._last_value = None

    def update(self, value):
        current = float(value)
        if self._last_value is None:
            self._last_value = current
            return current
        delta = current - self._last_value
        if delta > self.max_delta:
            current = self._last_value + self.max_delta
        elif delta < -self.max_delta:
            current = self._last_value - self.max_delta
        self._last_value = current
        return current


class LowPassFilter:
    """一阶低通滤波器

    @brief 使用固定 alpha 平滑输入
    """

    def __init__(self, alpha=0.2, initial=0.0):
        self.alpha = float(alpha)
        self._value = float(initial)

    def update(self, value):
        current = float(value)
        self._value = self.alpha * current + (1.0 - self.alpha) * self._value
        return self._value


class SpeedFilterChain:
    """速度输入滤波链

    @brief 保留先抑制尖峰, 再做差值限幅的顺序
    """

    def __init__(self, spike_window=5, max_delta=5.0):
        self.spike_filter = SpikeMedianFilter(window=spike_window)
        self.diff_filter = DiffLimitFilter(max_delta=max_delta)

    def update(self, value):
        filtered = self.spike_filter.update(float(value))
        return float(self.diff_filter.update(filtered))


def build_speed_filter_chain():
    """构造速度滤波链

    @brief 保留 legacy 的尖峰抑制和差值限幅顺序
    @return SpeedFilterChain
    """

    return SpeedFilterChain()


def build_gyro_filter(alpha=0.2):
    """构造角速度低通滤波器

    @brief 保留 yaw rate 的一阶低通语义
    @param alpha 低通系数
    @return LowPassFilter
    """

    return LowPassFilter(alpha=alpha, initial=0.0)
