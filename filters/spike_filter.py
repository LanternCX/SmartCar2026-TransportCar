"""尖峰中值滤波器.

用于去除速度或其他传感器数据中的突发尖峰噪声.
"""


class SpikeMedianFilter:
    """固定小窗口的中值滤波器,用于抑制尖峰异常值.
    
    通过维护一个固定大小的滑动窗口并输出其中值,可以有效
    去除单点离群值而保留有效的信号变化.
    """

    def __init__(self, window=3):
        """初始化尖峰中值滤波器.
        
        参数:
            window: 窗口大小(至少 3);若为偶数,会增加 1 使其为奇数.
        """
        self.window = max(3, int(window) or 3)
        if self.window % 2 == 0:
            self.window += 1  # 保持窗口大小为奇数
        self.buf = []

    def reset(self, value=None):
        """重置滤波器缓冲区.
        
        参数:
            value: 初始填充值(可选);若为 None,清空缓冲区.
        """
        self.buf = [] if value is None else [value] * self.window

    def update(self, new_val):
        """更新滤波器并返回中值.
        
        参数:
            new_val: 新的输入值.
        
        返回:
            当前缓冲区的中值.
        """
        if len(self.buf) >= self.window:
            self.buf.pop(0)
        self.buf.append(new_val)
        # 计算当前缓冲区的中值
        sorted_buf = sorted(self.buf)
        mid = len(sorted_buf) // 2
        return sorted_buf[mid]
