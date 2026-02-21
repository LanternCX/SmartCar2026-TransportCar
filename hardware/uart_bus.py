"""UART 初始化封装."""
from machine import UART


def create_uart3():
    """创建并初始化 UART3.
    
    UART3 用于数据采样和调试输出,波特率 115200.
    
    返回:
        UART(2) 对象,已初始化至 115200 bps.
    """
    uart3 = UART(2)
    uart3.init(115200)
    return uart3


def create_uart6():
    """创建并初始化 UART6.
    
    UART6 用于命令接收和查询响应,波特率 115200.
    
    返回:
        UART(5) 对象,已初始化至 115200 bps.
    """
    uart6 = UART(5)
    uart6.init(115200)
    return uart6
