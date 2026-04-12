"""辅车滤波能力入口.

@file src/assistant/ctrl/filters.py
"""


def _clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


class LowPassFilter:
    """保存跨周期低通滤波状态."""

    def __init__(self, alpha, initial=0.0):
        self.alpha = float(alpha)
        self.state = float(initial)
        self.initialized = False

    def update(self, value):
        """推进低通滤波状态.

        @brief 首次采样直接对齐输入, 后续再按 alpha 平滑更新。
        """

        next_value = float(value)
        if not self.initialized:
            self.state = next_value
            self.initialized = True
            return self.state
        self.state = ((1.0 - self.alpha) * self.state) + (self.alpha * next_value)
        return self.state


class SpikeMedianFilter:
    """压制尖峰脉冲, 避免编码器瞬时跳变直接进入控制链."""

    def __init__(self, window):
        self.window = max(3, int(window) or 3)
        if self.window % 2 == 0:
            self.window += 1
        self.buf = []

    def update(self, value):
        """用中值窗压制孤立尖峰.

        @brief 让编码器单拍异常不会直接进入后续差分和回归链路。
        """

        if len(self.buf) >= self.window:
            self.buf.pop(0)
        self.buf.append(float(value))
        ordered = sorted(self.buf)
        return ordered[len(ordered) // 2]


class DiffLimitFilter:
    """限制相邻采样差值, 避免异常增量拉坏回归预测."""

    def __init__(self, max_delta):
        self.max_delta = abs(float(max_delta))
        self.prev = None

    def update(self, value):
        """限制相邻采样的变化幅度.

        @brief 在进入回归预测前先削掉不可信的突变增量。
        """

        next_value = float(value)
        if self.prev is None:
            self.prev = next_value
            return next_value
        lower = self.prev - self.max_delta
        upper = self.prev + self.max_delta
        next_value = _clamp(next_value, lower, upper)
        self.prev = next_value
        return next_value


class DualWindowRegressionFilter:
    """组合短窗与长窗预测, 在响应速度和稳定性之间折中."""

    def __init__(self, tick_ms, long_window, short_window, combine_w=0.65):
        self.tick_ms = int(tick_ms)
        self.long_window = int(long_window)
        self.short_window = int(short_window)
        self.combine_w = float(combine_w)
        self.elapsed_ms = 0.0
        self.long_values = []
        self.short_values = []

    @staticmethod
    def _predict(window, next_t):
        """根据窗口采样预测下一拍值.

        @brief 用最小二乘拟合给长窗和短窗提供统一预测结果。
        """

        count = len(window)
        if count == 0:
            return 0.0
        if count == 1:
            return float(window[0][1])
        sum_t = 0.0
        sum_t2 = 0.0
        sum_y = 0.0
        sum_ty = 0.0
        for stamp, value in window:
            sample_t = float(stamp)
            sample_y = float(value)
            sum_t += sample_t
            sum_t2 += sample_t * sample_t
            sum_y += sample_y
            sum_ty += sample_t * sample_y
        denom = (count * sum_t2) - (sum_t * sum_t)
        if denom == 0.0:
            return float(window[-1][1])
        slope = ((count * sum_ty) - (sum_t * sum_y)) / denom
        intercept = (sum_y - (slope * sum_t)) / count
        return (slope * next_t) + intercept

    def update(self, value, dt_s=None):
        """推进双窗回归滤波器.

        @brief 同时维护长短两个时间窗, 在响应速度和稳态抖动之间折中。
        """

        if dt_s is None or float(dt_s) <= 0.0:
            dt_ms = float(self.tick_ms)
        else:
            dt_ms = float(dt_s) * 1000.0
        self.elapsed_ms += dt_ms
        stamp = float(self.elapsed_ms)
        pair = (stamp, float(value))
        self.long_values.append(pair)
        self.short_values.append(pair)
        if len(self.long_values) > self.long_window:
            self.long_values.pop(0)
        if len(self.short_values) > self.short_window:
            self.short_values.pop(0)
        next_t = float(self.elapsed_ms + dt_ms)
        long_pred = self._predict(self.long_values, next_t)
        short_pred = self._predict(self.short_values, next_t)
        return (short_pred * self.combine_w) + (long_pred * (1.0 - self.combine_w))


class SpeedFilterChain:
    """封装单路轮速滤波链的公开入口."""

    def __init__(self, window, max_delta, tick_ms, long_window, short_window):
        self.spike = SpikeMedianFilter(window)
        self.diff = DiffLimitFilter(max_delta)
        self.dt_s = None
        self.reg = DualWindowRegressionFilter(
            tick_ms=tick_ms,
            long_window=long_window,
            short_window=short_window,
        )

    def update(self, value):
        """依次执行尖峰抑制、差分限幅和回归预测.

        @brief 统一给单轮轮速提供一个可直接复用的滤波入口。
        """

        filtered = self.spike.update(value)
        filtered = self.diff.update(filtered)
        return self.reg.update(filtered, dt_s=self.dt_s)


def build_speed_filter_chain(
    window=5,
    max_delta=5.0,
    tick_ms=5,
    long_window=30,
    short_window=8,
):
    """构造单路轮速滤波公开入口.

    @brief 把单轮滤波链的默认窗口和预测参数集中收口在这里。
    """

    return SpeedFilterChain(
        window=window,
        max_delta=max_delta,
        tick_ms=tick_ms,
        long_window=long_window,
        short_window=short_window,
    )


def build_wheel_filter_bank(
    tick_ms,
    wheel_names,
    window,
    max_delta,
    long_window,
    short_window,
):
    """按轮位构造滤波链集合.

    @brief 统一为三轮底盘准备同口径的滤波对象, 但 owner 仍由状态层持有。
    """

    wheel_filters = {}
    for name in wheel_names:
        wheel_filters[name] = build_speed_filter_chain(
            window=window,
            max_delta=max_delta,
            tick_ms=tick_ms,
            long_window=long_window,
            short_window=short_window,
        )
    return wheel_filters


def set_wheel_filter_dt_s(filter_bank, wheel_names, dt_s):
    """给全部轮速滤波链同步当前拍长.

    @brief 让回归预测与实际调度周期保持一致。
    """

    for name in wheel_names:
        filter_chain = filter_bank.get(name)
        if filter_chain is not None:
            filter_chain.dt_s = dt_s


def update_wheel_speeds(filter_bank, raw_ticks, wheel_names):
    """执行单拍轮速滤波计算.

    @brief 按轮位读取原始计数并返回当前拍的滤波结果。
    """

    wheel_speeds = {}
    for name in wheel_names:
        wheel_speeds[name] = float(filter_bank[name].update(raw_ticks[name]))
    return wheel_speeds
