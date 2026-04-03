"""辅车滤波工具

@file src/assistant/stability/filtering.py
"""


class SpikeMedianFilter:
    """尖峰抑制滤波器

    @brief 使用滑动窗口中值抑制单点异常值
    """

    def __init__(self, window=5):
        # 窗口长度决定中值滤波参与计算的历史样本数
        self.window = max(1, int(window))
        self._values = []

    def update(self, value):
        """更新尖峰抑制滤波器

        @brief 返回当前窗口的中值结果
        @param value 原始输入
        @return float
        """

        self._values.append(float(value))
        if len(self._values) > self.window:
            del self._values[0]
        ordered = sorted(self._values)
        middle = len(ordered) // 2
        return float(ordered[middle])


class DiffLimitFilter:
    """差值限幅滤波器

    @brief 限制连续两次输出之间的最大跳变
    """

    def __init__(self, max_delta=5.0):
        # 限幅阈值和上一拍输出共同决定当前允许的变化范围
        self.max_delta = float(max_delta)
        self._last_value = None

    def update(self, value):
        """更新差值限幅滤波器

        @brief 限制当前输出相对上一拍的最大跳变
        @param value 原始输入
        @return float
        """

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

    @brief 用固定 alpha 平滑角速度输入
    """

    def __init__(self, alpha=0.2, initial=0.0):
        # 低通系数和初值决定滤波器的响应速度和初始状态
        self.alpha = float(alpha)
        self._value = float(initial)

    def update(self, value):
        """更新低通滤波器

        @brief 按一阶低通公式平滑输入
        @param value 原始输入
        @return float
        """

        current = float(value)
        self._value = self.alpha * current + (1.0 - self.alpha) * self._value
        return self._value


class SpeedFilterChain:
    """速度输入滤波链

    @brief 先抑制尖峰, 再限制相邻输出变化
    """

    def __init__(self, spike_window=5, max_delta=5.0):
        # 速度滤波链固定由中值滤波和差值限幅两段组成
        self.spike_filter = SpikeMedianFilter(window=spike_window)
        self.diff_filter = DiffLimitFilter(max_delta=max_delta)

    def update(self, value):
        """更新速度滤波链

        @brief 返回经过尖峰抑制和限幅后的结果
        @param value 原始输入
        @return float
        """

        filtered = self.spike_filter.update(float(value))
        return float(self.diff_filter.update(filtered))


def build_speed_filter_chain():
    """构造速度滤波链

    @brief 构造速度输入使用的默认滤波链
    @return SpeedFilterChain
    """

    return SpeedFilterChain()


def build_gyro_filter(alpha=0.2):
    """构造角速度低通滤波器

    @brief 构造角速度输入使用的一阶低通滤波器
    @param alpha 低通系数
    @return LowPassFilter
    """

    return LowPassFilter(alpha=alpha, initial=0.0)
