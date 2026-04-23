"""双窗口线性回归滤波器

通过长短两个滑动窗口进行线性回归, 结合两者预测值来平衡平滑性与响应速度
"""


class DualWindowRegressionFilter:
    """双窗口线性回归平滑器, 用于减少转角处的过冲

    - 短窗口跟踪快速变化; 长窗口提供稳定性
    - 对两个窗口分别进行线性回归, 预测下一时刻的值
    - 通过加权组合两者的预测值得到最终输出
    """

    def __init__(
        self,
        tick_ms=10,
        long_window=30,
        short_window=8,
        combine_w=0.65,
    ):
        """初始化双窗口线性回归滤波器

        @brief 配置采样周期、窗口大小及融合权重
        @param tick_ms 采样周期(毫秒)
        @param long_window 长窗口大小(样本数)
        @param short_window 短窗口大小(样本数)
        @param combine_w 短窗口在融合中的权重 [0, 1]; 默认 0.65
        """
        self.tick_ms = tick_ms
        self.long_window = long_window
        self.short_window = short_window
        self.combine_w = combine_w

        self.sample_idx = 0

        # 长窗口状态
        self.vals = [0.0] * long_window
        self.stamps = [0.0] * long_window
        self.idx = 0
        self.count = 0
        self.sum_t = 0.0
        self.sum_t2 = 0.0
        self.sum_y = 0.0
        self.sum_ty = 0.0

        # 短窗口状态
        self.s_vals = [0.0] * short_window
        self.s_stamps = [0.0] * short_window
        self.s_idx = 0
        self.s_count = 0
        self.s_sum_t = 0.0
        self.s_sum_t2 = 0.0
        self.s_sum_y = 0.0
        self.s_sum_ty = 0.0

    def _update_window(
        self,
        val,
        t_ms,
        buf,
        tbuf,
        idx,
        count,
        sum_t,
        sum_t2,
        sum_y,
        sum_ty,
        max_len,
    ):
        """更新一个滑动窗口的统计数据

        @brief 将新样本加入窗口并增量维护线性回归所需的累积统计量
        @param val 新值
        @param t_ms 时间戳
        @param buf 值缓冲区
        @param tbuf 时间戳缓冲区
        @param idx 当前写入位置
        @param count 已填充样本数
        @param sum_t 时间戳之和
        @param sum_t2 时间戳平方之和
        @param sum_y 值之和
        @param sum_ty 值与时间戳乘积之和
        @param max_len 窗口最大大小
        @return 更新后的 (idx, count, sum_t, sum_t2, sum_y, sum_ty)
        """
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
        """进行线性回归, 计算斜率和截距

        @brief 基于累积统计量求解最小二乘拟合的斜率与截距
        @param count 样本数
        @param sum_t 时间戳之和
        @param sum_t2 时间戳平方之和
        @param sum_y 值之和
        @param sum_ty 值与时间戳乘积之和
        @return 元组 (斜率, 截距)
        """
        denom = count * sum_t2 - sum_t * sum_t
        if denom != 0:
            slope = (count * sum_ty - sum_t * sum_y) / denom
            intercept = (sum_y - slope * sum_t) / count
        else:
            slope = 0.0
            intercept = 0.0
        return slope, intercept

    def reset(self):
        """重置滤波器状态

        @brief 清空所有窗口及累积统计量
        """
        self.sample_idx = 0
        self.idx = self.count = 0
        self.sum_t = self.sum_t2 = self.sum_y = self.sum_ty = 0.0

        self.s_idx = self.s_count = 0
        self.s_sum_t = self.s_sum_t2 = self.s_sum_y = self.s_sum_ty = 0.0

    def update(self, raw_value):
        """更新滤波器并返回平滑速度、加速度、斜率

        @brief 将新样本加入长短窗口, 分别回归后加权融合预测下一时刻状态
        @param raw_value 原始输入值
        @return 元组 (融合速度, 加速度, 融合斜率)
        """
        value = raw_value

        t_ms = self.sample_idx * self.tick_ms
        self.sample_idx += 1

        # 更新长窗口
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

        # 更新短窗口
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

        # 对两个窗口进行回归(若短窗口样本不足, 使用长窗口斜率)
        slope_long, intercept_long = self._regression(self.count, self.sum_t, self.sum_t2, self.sum_y, self.sum_ty)
        slope_short, intercept_short = self._regression(self.s_count, self.s_sum_t, self.s_sum_t2, self.s_sum_y, self.s_sum_ty)

        if self.s_count < 2:
            slope_short, intercept_short = slope_long, intercept_long

        # 预测下一时刻的值
        next_t = (self.sample_idx + 1) * self.tick_ms
        pred_long = slope_long * next_t + intercept_long
        pred_short = slope_short * next_t + intercept_short

        fused_speed = pred_short * self.combine_w + pred_long * (1 - self.combine_w)
        fused_slope = slope_short * self.combine_w + slope_long * (1 - self.combine_w)
        accel = fused_slope * 1000.0  # 转换为每秒的加速度

        return fused_speed, accel, fused_slope
