from typing import Any, Callable, Sequence

class ticker:
    """周期性定时器中断，用于同步采样。
    
    示例:
        pit = ticker(1)
        pit.callback(on_tick)
        pit.capture_list(encoder1, encoder2)
        pit.start(10)  # 10ms 周期
    """
    def __init__(self, index: int) -> None:
        """使用给定索引初始化 ticker (0-3)。
        
        Args:
            index: Ticker 索引 (0-3)
        """
    def start(self, period_ms: int) -> None:
        """使用给定周期启动 ticker。
        
        Args:
            period_ms: 周期，单位毫秒
        """
    def stop(self) -> None:
        """停止 ticker。"""
    def callback(self, func: Callable[[Any], Any]) -> None:
        """设置在每个 tick 时调用的回调函数。
        
        Args:
            func: 回调函数，接收 ticker 实例作为参数
        """
    def capture_list(self, *items: Any) -> None:
        """关联传感器/编码器进行同步采集。
        
        Args:
            *items: 传感器/编码器对象 (最多 8 个)
        """

class encoder:
    """旋转编码器接口，用于速度测量。
    
    示例:
        enc = encoder('D15', 'D16', invert=True)
        speed = enc.get()
    """
    def __init__(self, phase_a: str, phase_b: str, invert: bool = False) -> None:
        """在两个引脚上初始化编码器。
        
        Args:
            phase_a: A 相引脚名称
            phase_b: B 相引脚名称
            invert: 是否反转旋转方向
        """
    def capture(self) -> None:
        """触发一次采集（通常由 ticker 管理）。"""
    def get(self) -> list[int]:
        """获取编码器读数。
        
        Returns:
            编码器计数/速度值
        """
    def read(self) -> list[int]:
        """采集并获取编码器读数。
        
        Returns:
            编码器计数/速度值
        """

class ADC_Group:
    """将多个 ADC 通道分组用于同步采样。
    
    示例:
        adc = ADC_Group(1)
        adc.addch('B12')
        adc.addch('B14')
        values = adc.get()  # [val0, val1]
    """
    PMODE0: int  #: 采样周期模式 0
    PMODE1: int  #: 采样周期模式 1
    PMODE2: int  #: 采样周期模式 2
    PMODE3: int  #: 采样周期模式 3
    AVG1: int  #: 无平均
    AVG4: int  #: 4 次采样平均
    AVG8: int  #: 8 次采样平均
    AVG16: int  #: 16 次采样平均
    AVG32: int  #: 32 次采样平均
    def __init__(self, index: int) -> None:
        """初始化 ADC 组 (RT1021 上为 1 或 2)。
        
        Args:
            index: ADC 组索引 (1 或 2)
        """
    def addch(self, pin: str) -> None:
        """向组添加通道。
        
        Args:
            pin: 引脚名称 (例如 'B12')
        """
    def init(self, id: int, *, period: int = ..., average: int = ...) -> None:
        """配置 ADC 组。
        
        Args:
            id: 组索引 (1 或 2)
            period: 采样周期模式
            average: 平均模式
        """
    def capture(self) -> None:
        """触发一次采集（通常由 ticker 管理）。"""
    def get(self) -> list[int]:
        """获取 ADC 读数 (每个通道 0-4095)。
        
        Returns:
            每个通道的 ADC 值列表
        """
    def read(self) -> list[int]:
        """采集并获取 ADC 读数。
        
        Returns:
            每个通道的 ADC 值列表
        """

# Allow ad-hoc helpers without type noise
def __getattr__(name: str) -> Any: ...

__all__ = ["ticker", "encoder", "ADC_Group"]
