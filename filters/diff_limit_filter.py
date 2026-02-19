"""差值限幅滤波器.

限制相邻采样点的变化幅度,用于抑制速度等信号的突变.
"""
from typing import Union, Optional


class DiffLimitFilter:
    """限制单次采样变化量的滤波器.
    
    若新输入超出上一值的 ±max_delta 范围,则限制在该范围内,
    从而抑制突变同时保留缓慢变化.
    """

    def __init__(self, max_delta: Union[float, int]) -> None:
        """初始化差值限幅滤波器.
        
        参数:
            max_delta: 每个采样周期的最大允许变化量(取绝对值).
        """
        self.max_delta = abs(max_delta) if max_delta is not None else 0.0
        self.prev: Optional[Union[float, int]] = None

    def reset(self, value: Optional[Union[float, int]] = None) -> None:
        """重置滤波器状态.
        
        参数:
            value: 新的前一值(可选).
        """
        self.prev = value

    def update(self, new_val: Union[float, int]) -> Union[float, int]:
        """更新滤波器并返回限幅后的值.
        
        参数:
            new_val: 新的输入值.
        
        返回:
            限幅后的输出值.
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
