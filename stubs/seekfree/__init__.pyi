from typing import Any, Sequence

class TSL1401:
    """线性 CCD 阵列传感器，用于线迹跟踪。
    
    示例:
        ccd = TSL1401(10)  # 每 10 个 tick 采集一次
        ccd.set_resolution(TSL1401.RES_12BIT)
        pit.capture_list(ccd)
        data = ccd.get()
    """
    RES_8BIT: int  #: 8 位分辨率 (0-255)
    RES_12BIT: int  #: 12 位分辨率 (0-4095)
    def __init__(self, capture_div: int | None = None) -> None:
        """初始化 TSL1401 CCD 传感器。
        
        Args:
            capture_div: 采集分频 (每 N 个 ticker tick 更新一次)
        """
    def set_resolution(self, resolution: int) -> None:
        """设置 ADC 分辨率。
        
        Args:
            resolution: TSL1401.RES_8BIT 或 TSL1401.RES_12BIT
        """
    def capture(self) -> None:
        """触发一次采集（通常由 ticker 管理）。"""
    def get(self) -> list[int]:
        """获取 CCD 阵列数据。
        
        Returns:
            像素值列表 (128 个像素)
        """
    def read(self) -> list[int]:
        """采集并获取 CCD 数据。
        
        Returns:
            像素值列表 (128 个像素)
        """
    @classmethod
    def help(cls) -> None:
        """打印 TSL1401 的帮助信息。"""
    def info(self) -> None:
        """打印该 TSL1401 实例的信息。"""

class DL1X:
    """飞行时间 (ToF) 距离传感器。
    
    示例:
        tof = DL1X()
        pit.capture_list(tof)
        distance = tof.get()
    """
    def __init__(self, capture_div: int | None = None) -> None:
        """初始化 DL1X ToF 传感器。
        
        Args:
            capture_div: 采集分频 (每 N 个 ticker tick 更新一次)
        """
    def capture(self) -> None:
        """触发一次采集（通常由 ticker 管理）。"""
    def get(self) -> list[int] | int | float:
        """获取距离测量值。
        
        Returns:
            距离值 (单位为 mm 或 cm，取决于硬件)
        """
    def read(self) -> list[int] | int | float:
        """采集并获取距离测量值。
        
        Returns:
            距离值
        """
    @classmethod
    def help(cls) -> None:
        """打印 DL1X 的帮助信息。"""
    def info(self) -> None:
        """打印该 DL1X 实例的信息。"""

class IMU660RX:
    """6 轴 IMU (加速度计 + 陀螺仪)。
    
    示例:
        imu = IMU660RX()
        pit.capture_list(imu)
        data = imu.get()  # [ax, ay, az, gx, gy, gz]
    """
    def __init__(self, capture_div: int | None = None) -> None:
        """初始化 IMU660RX 传感器。
        
        Args:
            capture_div: 采集分频 (每 N 个 ticker tick 更新一次)
        """
    def capture(self) -> None:
        """触发一次采集（通常由 ticker 管理）。"""
    def get(self) -> list[int]:
        """获取 IMU 数据。
        
        Returns:
            [加速度_X, 加速度_Y, 加速度_Z, 角速度_X, 角速度_Y, 角速度_Z]
        """
    def read(self) -> list[int]:
        """采集并获取 IMU 数据。
        
        Returns:
            [加速度_X, 加速度_Y, 加速度_Z, 角速度_X, 角速度_Y, 角速度_Z]
        """
    @classmethod
    def help(cls) -> None:
        """打印 IMU660RX 的帮助信息。"""
    def info(self) -> None:
        """打印该 IMU660RX 实例的信息。"""

class IMU963RX:
    """9 轴 IMU (加速度计 + 陀螺仪 + 磁力计)。
    
    示例:
        imu = IMU963RX()
        pit.capture_list(imu)
        data = imu.get()  # [ax, ay, az, gx, gy, gz, mx, my, mz]
    """
    def __init__(self, capture_div: int | None = None) -> None:
        """初始化 IMU963RX 传感器。
        
        Args:
            capture_div: 采集分频 (每 N 个 ticker tick 更新一次)
        """
    def capture(self) -> None:
        """触发一次采集（通常由 ticker 管理）。"""
    def get(self) -> list[int]:
        """获取 IMU 数据。
        
        Returns:
            [加速度_X, 加速度_Y, 加速度_Z, 角速度_X, 角速度_Y, 角速度_Z, 磁力_X, 磁力_Y, 磁力_Z]
        """
    def read(self) -> list[int]:
        """采集并获取 IMU 数据。
        
        Returns:
            [加速度_X, 加速度_Y, 加速度_Z, 角速度_X, 角速度_Y, 角速度_Z, 磁力_X, 磁力_Y, 磁力_Z]
        """
    @classmethod
    def help(cls) -> None:
        """打印 IMU963RX 的帮助信息。"""
    def info(self) -> None:
        """打印该 IMU963RX 实例的信息。"""

class KEY_HANDLER:
    """按键/键盘输入处理器。
    
    示例:
        key = KEY_HANDLER()
        pit.capture_list(key)
        key_state = key.get()
    """
    def __init__(self, capture_div: int | None = None) -> None:
        """初始化按键处理器。
        
        Args:
            capture_div: 采集分频 (每 N 个 ticker tick 更新一次)
        """
    def capture(self) -> None:
        """触发一次采集（通常由 ticker 管理）。"""
    def get(self) -> list[int]:
        """获取按键状态。
        
        Returns:
            按键状态值
        """
    def read(self) -> list[int]:
        """采集并获取按键状态。
        
        Returns:
            按键状态值
        """
    @classmethod
    def help(cls) -> None:
        """打印 KEY_HANDLER 的帮助信息。"""
    def info(self) -> None:
        """打印该 KEY_HANDLER 实例的信息。"""

class WIFI_SPI:
    """WiFi 模块 SPI 接口。
    
    示例:
        wifi = WIFI_SPI()
        wifi.send(b"data")
        data = wifi.recv(100)
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化 WiFi SPI 接口。"""
    def send(self, buf: Sequence[int] | bytes | bytearray | str) -> None:
        """通过 WiFi 发送数据。
        
        Args:
            buf: 要发送的数据
        """
    def recv(self, nbytes: int) -> bytes:
        """从 WiFi 接收数据。
        
        Args:
            nbytes: 要接收的字节数
        
        Returns:
            接收到的数据
        """

class WIRELESS_UART:
    """无线 UART 模块接口。
    
    示例:
        wireless = WIRELESS_UART()
        wireless.send(b"data")
        data = wireless.recv(100)
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化无线 UART 接口。"""
    def send(self, buf: Sequence[int] | bytes | bytearray | str) -> None:
        """通过无线发送数据。
        
        Args:
            buf: 要发送的数据
        """
    def recv(self, nbytes: int) -> bytes:
        """从无线接收数据。
        
        Args:
            nbytes: 要接收的字节数
        
        Returns:
            接收到的数据
        """

class BLDC_CONTROLLER:
    """无刷电机控制器。
    
    示例:
        motor = BLDC_CONTROLLER()
        motor.set_speed(1000)
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化无刷电机控制器。"""
    def set_speed(self, duty: int) -> None:
        """设置电机速度。
        
        Args:
            duty: 速度值 (通常为 0-1000 或 0-100)
        """
    def stop(self) -> None:
        """停止电机。"""

class MOTOR_CONTROLLER:
    """直流电机控制器。
    
    示例:
        motor = MOTOR_CONTROLLER()
        motor.set_speed(500)
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化直流电机控制器。"""
    def set_speed(self, duty: int) -> None:
        """设置电机速度。
        
        Args:
            duty: 速度值 (通常为 0-1000 或 0-100)
        """
    def stop(self) -> None:
        """停止电机。"""

# Permit additional helpers without warnings
def __getattr__(name: str) -> Any: ...

__all__ = [
    "TSL1401",
    "DL1X",
    "IMU660RX",
    "IMU963RX",
    "KEY_HANDLER",
    "WIFI_SPI",
    "WIRELESS_UART",
    "BLDC_CONTROLLER",
    "MOTOR_CONTROLLER",
]
