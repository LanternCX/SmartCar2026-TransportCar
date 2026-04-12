"""低通滤波器.

实现单极点 IIR 低通滤波,采用一阶递推公式.
"""


class LowPassFilter:
    """单极点 IIR 低通滤波器.
    
    递推关系:state_new = (1 - alpha) * state_prev + alpha * input_new
    
    参数 alpha 越大,响应越快但噪声越多;alpha 越小,响应越慢但平滑.
    """

    def __init__(self, alpha=0.3, initial=None):
        """初始化低通滤波器.
        
        参数:
            alpha: 滤波系数 [0, 1],默认 0.3.
            initial: 初始状态值(可选).
        """
        self.alpha = alpha
        self.state = initial

    def reset(self, value=None):
        """重置滤波器状态.
        
        参数:
            value: 新的状态值(可选;若为 None,清空状态).
        """
        self.state = value

    def update(self, new_val):
        """更新滤波器并返回输出.
        
        参数:
            new_val: 新的输入值.
        
        返回:
            滤波后的输出值.
        """
        if self.state is None:
            self.state = new_val
        else:
            self.state = (1 - self.alpha) * self.state + self.alpha * new_val
        return self.state
