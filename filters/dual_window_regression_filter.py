class DualWindowRegressionFilter:
    """Dual-window linear regression smoother to reduce overshoot at corners.

    - Short window tracks fast changes; long window stabilizes.
    - Optional input low-pass to tame jitter before regression.
    """

    def __init__(
        self,
        tick_ms=10,
        long_window=30,
        short_window=8,
        combine_w=0.65,
    ):
        self.tick_ms = tick_ms
        self.long_window = long_window
        self.short_window = short_window
        self.combine_w = combine_w


        self.sample_idx = 0

        # Long window state
        self.vals = [0.0] * long_window
        self.stamps = [0.0] * long_window
        self.idx = 0
        self.count = 0
        self.sum_t = 0.0
        self.sum_t2 = 0.0
        self.sum_y = 0.0
        self.sum_ty = 0.0

        # Short window state
        self.s_vals = [0.0] * short_window
        self.s_stamps = [0.0] * short_window
        self.s_idx = 0
        self.s_count = 0
        self.s_sum_t = 0.0
        self.s_sum_t2 = 0.0
        self.s_sum_y = 0.0
        self.s_sum_ty = 0.0

    def _update_window(self, val, t_ms, buf, tbuf, idx, count, sum_t, sum_t2, sum_y, sum_ty, max_len):
        if count < max_len:
            buf[count] = val
            tbuf[count] = t_ms
            sum_t += t_ms
            sum_t2 += t_ms * t_ms
            sum_y += val
            sum_ty += val * t_ms
            count += 1
        else:
            old = buf[idx]
            old_t = tbuf[idx]
            sum_t -= old_t
            sum_t2 -= old_t * old_t
            sum_y -= old
            sum_ty -= old * old_t

            buf[idx] = val
            tbuf[idx] = t_ms
            sum_t += t_ms
            sum_t2 += t_ms * t_ms
            sum_y += val
            sum_ty += val * t_ms

            idx = (idx + 1) % max_len

        return idx, count, sum_t, sum_t2, sum_y, sum_ty

    @staticmethod
    def _regression(count, sum_t, sum_t2, sum_y, sum_ty):
        denom = count * sum_t2 - sum_t * sum_t
        if denom != 0:
            slope = (count * sum_ty - sum_t * sum_y) / denom
            intercept = (sum_y - slope * sum_t) / count
        else:
            slope = 0.0
            intercept = 0.0
        return slope, intercept

    def reset(self):
        self.sample_idx = 0
        self.idx = self.count = 0
        self.sum_t = self.sum_t2 = self.sum_y = self.sum_ty = 0.0

        self.s_idx = self.s_count = 0
        self.s_sum_t = self.s_sum_t2 = self.s_sum_y = self.s_sum_ty = 0.0

        # no input low-pass to reset

    def update(self, raw_value):
        # use raw input value
        value = raw_value

        t_ms = self.sample_idx * self.tick_ms
        self.sample_idx += 1

        # Update long window
        self.idx, self.count, self.sum_t, self.sum_t2, self.sum_y, self.sum_ty = self._update_window(
            value,
            t_ms,
            self.vals,
            self.stamps,
            self.idx,
            self.count,
            self.sum_t,
            self.sum_t2,
            self.sum_y,
            self.sum_ty,
            self.long_window,
        )

        # Update short window
        self.s_idx, self.s_count, self.s_sum_t, self.s_sum_t2, self.s_sum_y, self.s_sum_ty = self._update_window(
            value,
            t_ms,
            self.s_vals,
            self.s_stamps,
            self.s_idx,
            self.s_count,
            self.s_sum_t,
            self.s_sum_t2,
            self.s_sum_y,
            self.s_sum_ty,
            self.short_window,
        )

        # Regression for both windows (fall back to long slope if short not ready)
        slope_long, intercept_long = self._regression(self.count, self.sum_t, self.sum_t2, self.sum_y, self.sum_ty)
        slope_short, intercept_short = self._regression(self.s_count, self.s_sum_t, self.s_sum_t2, self.s_sum_y, self.s_sum_ty)

        if self.s_count < 2:
            slope_short, intercept_short = slope_long, intercept_long

        next_t = (self.sample_idx + 1) * self.tick_ms
        pred_long = slope_long * next_t + intercept_long
        pred_short = slope_short * next_t + intercept_short

        fused_speed = pred_short * self.combine_w + pred_long * (1 - self.combine_w)
        fused_slope = slope_short * self.combine_w + slope_long * (1 - self.combine_w)
        accel = fused_slope * 1000.0  # per second

        # return fused regression speed directly
        return fused_speed, accel, fused_slope
