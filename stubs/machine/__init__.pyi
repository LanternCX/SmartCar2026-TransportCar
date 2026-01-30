from typing import Any, Callable, Optional, Sequence

class Pin:
    """RT1021 GPIO 数字 I/O 接口。
    
    示例:
        led = Pin('C4', Pin.OUT, value=True)
        led.toggle()
        if pin.value() == 1:
            pin.low()
    """
    IN: int  #: 输入模式
    OUT: int  #: 输出模式
    OPEN_DRAIN: int  #: 开漏模式
    PULL_UP: int  #: 上拉电阻
    PULL_UP_47K: int  #: 47K 上拉
    PULL_UP_22K: int  #: 22K 上拉
    PULL_DOWN: int  #: 下拉电阻
    PULL_HOLD: int  #: 保持（Keeper）电阻
    DRIVE_OFF: int  #: 驱动强度关闭
    DRIVE_0: int  #: 驱动强度 0
    DRIVE_1: int  #: 驱动强度 1
    DRIVE_2: int  #: 驱动强度 2
    DRIVE_3: int  #: 驱动强度 3
    DRIVE_4: int  #: 驱动强度 4
    DRIVE_5: int  #: 驱动强度 5
    DRIVE_6: int  #: 驱动强度 6
    def __init__(self, id: str | int, mode: int, *, pull: Optional[int] = ..., value: int | bool | None = None, drive: Optional[int] = None) -> None:
        """初始化 GPIO 引脚。
        
        Args:
            id: 引脚名称 (例如 'C4', 'D9') 或引脚编号
            mode: Pin.IN、Pin.OUT 或 Pin.OPEN_DRAIN
            pull: 可选的上/下拉电阻 (PULL_UP_47K、PULL_DOWN 等)
            value: 输出引脚的初始电平 (0 或 1)
            drive: 驱动强度 (DRIVE_0 到 DRIVE_6)
        """
    def on(self) -> None:
        """将引脚设为高电平。"""
    def off(self) -> None:
        """将引脚设为低电平。"""
    def low(self) -> None:
        """将引脚设为低电平（同 off）。"""
    def high(self) -> None:
        """将引脚设为高电平（同 on）。"""
    def toggle(self) -> None:
        """切换引脚电平。"""
    def value(self, x: int | bool | None = None) -> int:
        """获取或设置引脚电平值。返回 0（低）或 1（高）。
        
        Args:
            x: 如果提供，将引脚设为该值；如果为 None，返回当前值
        
        Returns:
            当前引脚电平值 (0 或 1)
        """
    def irq(self, handler: Callable[[Any], Any] | None = None, trigger: int | None = None) -> None:
        """配置 GPIO 中断处理程序。
        
        Args:
            handler: 在中断时执行的回调函数
            trigger: 中断触发类型
        """

class UART:
    """UART 串口通信接口。
    
    示例:
        uart = UART(5)  # LPUART6
        uart.init(460800)
        uart.write(b"Hello")
        data = uart.read(10)
    """
    def __init__(self, id: int, *args: Any, **kwargs: Any) -> None:
        """使用给定 ID 初始化 UART (RT1021 上为 0-7)。
        
        Args:
            id: UART ID (0=LPUART1, 1=LPUART2, ..., 7=LPUART8)
        """
    def init(self, baudrate: int = ..., bits: int = ..., parity: Optional[int] = ..., stop: int = ..., *args: Any, **kwargs: Any) -> None:
        """配置 UART 参数。
        
        Args:
            baudrate: 波特率 (默认 9600)
            bits: 数据位数 (默认 8)
            parity: 校验模式 (None、0=偶校验、1=奇校验)
            stop: 停止位数 (默认 1)
        """
    def any(self) -> int:
        """返回可读取的字节数。"""
    def read(self, nbytes: int | None = None) -> bytes | None:
        """从 UART 读取最多 nbytes 字节。
        
        Args:
            nbytes: 要读取的字节数；如果为 None，读取所有可用数据
        
        Returns:
            读取的字节数据，或无数据时返回 None
        """
    def readinto(self, buf: bytearray) -> int | None:
        """读取数据到缓冲区。
        
        Args:
            buf: 要读入的缓冲区
        
        Returns:
            读取的字节数
        """
    def write(self, buf: Sequence[int] | bytes | bytearray | str) -> int | None:
        """向 UART 写入数据。
        
        Args:
            buf: 要写入的数据 (字节、bytearray 或字符串)
        
        Returns:
            写入的字节数
        """

class SPI:
    """SPI 串行接口用于传感器/设备通信。
    
    示例:
        spi = SPI(1)  # LPSPI2
        spi.init(baudrate=1000000, polarity=0, phase=0)
        spi.write(b'data')
        result = spi.read(4)
    """
    def __init__(self, id: int, *args: Any, **kwargs: Any) -> None:
        """使用给定 ID 初始化 SPI (RT1021 上为 0-3)。
        
        Args:
            id: SPI ID (0=LPSPI1, 1=LPSPI2, 2=LPSPI3, 3=LPSPI4)
        """
    def init(self, baudrate: int = ..., polarity: int = ..., phase: int = ..., *args: Any, **kwargs: Any) -> None:
        """配置 SPI 参数。
        
        Args:
            baudrate: 时钟频率，单位 Hz (默认 1000000)
            polarity: 时钟极性 (0=空闲时低电平, 1=空闲时高电平)
            phase: 时钟相位 (0=第一个边沿采样, 1=第二个边沿采样)
        """
    def read(self, nbytes: int, write: int | None = None) -> bytes:
        """从 SPI 读取字节 (发送 0x00)。
        
        Args:
            nbytes: 要读取的字节数
            write: 读取期间发送的字节 (默认 0x00)
        
        Returns:
            从 SPI 读取的字节
        """
    def readinto(self, buf: bytearray) -> None:
        """读取 SPI 数据到缓冲区。
        
        Args:
            buf: 要读入的缓冲区
        """
    def write(self, buf: Sequence[int] | bytes | bytearray | str) -> None:
        """向 SPI 写入数据。
        
        Args:
            buf: 要发送的数据
        """
    def write_readinto(self, out: Sequence[int] | bytes | bytearray | str, inp: bytearray) -> None:
        """同时向 SPI 写入和读取数据。
        
        Args:
            out: 要发送的数据
            inp: 接收数据的缓冲区 (必须与 out 长度相同)
        """

class I2C:
    """I2C 接口用于传感器/设备通信。
    
    示例:
        i2c = I2C(3, freq=100000)  # LPI2C4
        devices = i2c.scan()
        i2c.writeto(0x68, b'\\x3b')
        data = i2c.readfrom(0x68, 6)
    """
    def __init__(self, id: int, freq: int = 400000, *args: Any, **kwargs: Any) -> None:
        """使用给定 ID 初始化 I2C (RT1021 上为 0-3)。
        
        Args:
            id: I2C ID (0=LPI2C1, 1=LPI2C2, 2=LPI2C3, 3=LPI2C4)
            freq: 时钟频率，单位 Hz (默认 400000)
        """
    def scan(self) -> list[int]:
        """扫描 I2C 总线寻找连接的设备。
        
        Returns:
            找到的设备地址列表 (0x08-0x77)
        """
    def readfrom(self, addr: int, nbytes: int, stop: bool = True) -> bytes:
        """从 I2C 设备读取数据。
        
        Args:
            addr: 设备 I2C 地址
            nbytes: 要读取的字节数
            stop: 读取后是否发送停止信号
        
        Returns:
            从设备读取的字节
        """
    def readfrom_into(self, addr: int, buf: bytearray, stop: bool = True) -> None:
        """读取 I2C 数据到缓冲区。
        
        Args:
            addr: 设备 I2C 地址
            buf: 要读入的缓冲区
            stop: 读取后是否发送停止信号
        """
    def writeto(self, addr: int, buf: Sequence[int] | bytes | bytearray, stop: bool = True) -> int:
        """向 I2C 设备写入数据。
        
        Args:
            addr: 设备 I2C 地址
            buf: 要写入的数据
            stop: 写入后是否发送停止信号
        
        Returns:
            写入的字节数
        """
    def writevto(self, addr: int, vectors: Sequence[Sequence[int] | bytes | bytearray], stop: bool = True) -> int:
        """向 I2C 设备写入多个数据向量。
        
        Args:
            addr: 设备 I2C 地址
            vectors: 要写入的数据缓冲区列表
            stop: 写入后是否发送停止信号
        
        Returns:
            写入的字节数
        """

class PWM:
    """PWM 输出用于舵机控制、电机驱动或 LED 亮度调节。
    
    示例:
        pwm = PWM('C20', 300, duty_u16=32768)  # 50% 占空比
        pwm.duty_u16(49152)  # 75% 占空比
        pwm.freq(1000)
    """
    def __init__(self, pin: str | int, freq: int, duty_u16: int, *args: Any, **kwargs: Any) -> None:
        """在引脚上初始化 PWM。
        
        Args:
            pin: 引脚名称 (例如 'C20') 或引脚编号
            freq: 频率，单位 Hz
            duty_u16: 初始占空比 (0-65535，其中 65535=100%)
        """
    def duty_u16(self, value: int | None = None) -> int:
        """获取或设置 PWM 占空比。
        
        Args:
            value: 占空比 (0-65535)；如果为 None，返回当前值
        
        Returns:
            当前占空比值
        """
    def freq(self, value: int | None = None) -> int:
        """获取或设置 PWM 频率。
        
        Args:
            value: 频率，单位 Hz；如果为 None，返回当前值
        
        Returns:
            当前频率，单位 Hz
        """

class ADC:
    """模数转换器用于读取模拟传感器。
    
    示例:
        adc = ADC('B27')
        value = adc.read_u16()  # 0-65535
    """
    def __init__(self, pin: str | int, *args: Any, **kwargs: Any) -> None:
        """在引脚上初始化 ADC。
        
        Args:
            pin: ADC 引脚名称 (例如 'B27') 或引脚编号
        """
    def read_u16(self) -> int:
        """读取模拟值。
        
        Returns:
            ADC 值 (0-65535，其中 65535 = 3.3V)
        """

class Timer:
    """定时器/中断接口。
    
    示例:
        timer = Timer(0)
        timer.init(period=1000, mode=Timer.PERIODIC, callback=handler)
    """
    PERIODIC: int  #: 周期性（重复）定时器
    ONE_SHOT: int  #: 一次性定时器
    def __init__(self, id: int, *args: Any, **kwargs: Any) -> None:
        """使用给定 ID 初始化定时器。
        
        Args:
            id: 定时器 ID
        """
    def init(self, period: int, mode: int | None = None, callback: Callable[[Any], Any] | None = None) -> None:
        """配置定时器。
        
        Args:
            period: 定时器周期，单位毫秒
            mode: Timer.PERIODIC 或 Timer.ONE_SHOT
            callback: 定时器触发时调用的函数
        """
    def deinit(self) -> None:
        """停止并禁用定时器。"""

# Generic helpers for other board-specific symbols
board_id: str

# OS 模块用于文件系统操作
class _OSModule:
    """文件系统操作模块。
    
    示例:
        os.chdir("/flash")
        files = os.listdir()
        os.remove("file.txt")
    """
    def chdir(self, path: str) -> None:
        """更改当前目录。
        
        Args:
            path: 目录路径
        """
    def getcwd(self) -> str:
        """获取当前工作目录。
        
        Returns:
            当前目录路径
        """
    def listdir(self, path: str = ".") -> list[str]:
        """列出目录内容。
        
        Args:
            path: 目录路径 (默认为当前目录)
        
        Returns:
            文件/文件夹名称列表
        """
    def mkdir(self, path: str) -> None:
        """创建目录。
        
        Args:
            path: 目录路径
        """
    def remove(self, path: str) -> None:
        """删除文件。
        
        Args:
            path: 文件路径
        """
    def rename(self, src: str, dst: str) -> None:
        """重命名或移动文件。
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
        """
    def rmdir(self, path: str) -> None:
        """移除目录。
        
        Args:
            path: 目录路径
        """
    def stat(self, path: str) -> tuple[int, int, int, int, int, int, int, int, int, int]:
        """获取文件统计信息。
        
        Args:
            path: 文件路径
        
        Returns:
            文件状态信息元组
        """
    def urandom(self, n: int) -> bytes:
        """获取随机字节。
        
        Args:
            n: 字节数
        
        Returns:
            随机字节
        """

os: _OSModule  #: 文件系统操作模块

def execfile(filename: str) -> Any:
    """执行一个 Python 文件。
    
    Args:
        filename: 要执行的 Python 文件路径
    
    Returns:
        执行结果
    """

__all__ = ["Pin", "UART", "SPI", "I2C", "PWM", "ADC", "Timer", "board_id", "os", "execfile"]
