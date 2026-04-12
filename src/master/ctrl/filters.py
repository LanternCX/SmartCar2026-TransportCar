"""主车滤波能力入口.

@file src/master/ctrl/filters.py
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
        """推进低通滤波状态并返回当前输出.

        @brief 首拍直接吸收输入, 后续才按 alpha 融合, 这样初始化阶段不会被旧默认值拖偏。
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
        """把尖峰值压回局部中位数.

        @brief 先在输入端抑制单拍毛刺, 避免后续差分限幅和回归预测被异常点带偏。
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
        """限制相邻样本的变化幅度.

        @brief 这个阶段专门处理跳边和误码, 让后面的回归窗只看到可接受的增量。
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
        self.tail = DualWindowRegressionFilter(
            tick_ms=tick_ms,
            long_window=long_window,
            short_window=short_window,
        )

    def update(self, value):
        """按既定顺序执行单路轮速滤波链.

        @brief 先压尖峰、再限差分、最后做双窗回归, 保持所有轮位使用一致处理链。
        """

        filtered = self.spike.update(value)
        filtered = self.diff.update(filtered)
        return self.tail.update(filtered)


def build_speed_filter_chain(
    window=5,
    max_delta=5.0,
    tick_ms=5,
    long_window=30,
    short_window=8,
):
    """构造单路轮速滤波公开入口.

    @brief 把一组滤波参数固化成可复用对象, 供各轮按同样口径装配。
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
    """按轮位构造滤波链, 但对象 owner 仍由状态层持有.

    @brief 这里负责批量装配, 不负责保存跨周期状态引用。
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


def update_wheel_speeds(filter_bank, raw_ticks, wheel_names):
    """执行单拍滤波计算, 返回每个轮位的滤波结果.

    @brief 统一把原始脉冲样本推进到各轮滤波链, 给速度环提供同拍结果。
    """

    wheel_speeds = {}
    for name in wheel_names:
        wheel_speeds[name] = float(filter_bank[name].update(raw_ticks[name]))
    return wheel_speeds
