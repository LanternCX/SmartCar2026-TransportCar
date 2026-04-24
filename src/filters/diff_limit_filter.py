"""差值限幅滤波器

限制相邻采样点的变化幅度, 用于抑制速度等信号的突变
"""


class DiffLimitFilter:
    """限制单次采样变化量的滤波器

    若新输入超出上一值的 ±max_delta 范围, 则限制在该范围内,
    从而抑制突变同时保留缓慢变化
    """

    def __init__(self, max_delta):
        """初始化差值限幅滤波器

        @brief 设置允许的最大单步变化量
        @param max_delta 每个采样周期的最大允许变化量(取绝对值)
        """
        self.max_delta = abs(max_delta) if max_delta is not None else 0.0
        self.prev = None

    def reset(self, value=None):
        """重置滤波器状态

        @brief 将前一值重置为指定值或清空
        @param value 新的前一值(可选)
        """
        self.prev = value

    def update(self, new_val):
        """更新滤波器并返回限幅后的值

        @brief 对输入进行变化量限制, 防止信号突变
        @param new_val 新的输入值
        @return 限幅后的输出值
        """
        if self.prev is None:
            self.prev = new_val
            return new_val
        if self.max_delta <= 0:
            self.prev = new_val
            return new_val
        lo = self.prev - self.max_delta
        hi = self.prev + self.max_delta
        if new_val < lo:
            new_val = lo
        elif new_val > hi:
            new_val = hi
        self.prev = new_val
        return new_val
