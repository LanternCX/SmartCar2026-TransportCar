"""UART 总线初始化封装

提供三条 UART 总线的工厂函数, 分别服务于控制命令、主辅车通信和本车本地视觉链路
"""

from config import comm as comm_params
from machine import UART


UART_BAUDRATE = getattr(comm_params, "UART_BAUDRATE")
UART3_PORT_ID = getattr(comm_params, "UART3_PORT_ID")
UART6_PORT_ID = getattr(comm_params, "UART6_PORT_ID")
UART8_PORT_ID = getattr(comm_params, "UART8_PORT_ID")


def create_uart3():
    """@brief 创建并初始化 UART3

    UART3 承担上游控制命令与查询回包的传输职责

    @return 已初始化至配置波特率的 UART3 对象
    """
    uart3 = UART(UART3_PORT_ID)
    uart3.init(UART_BAUDRATE)
    return uart3


def create_uart8():
    """@brief 创建并初始化 UART8

    UART8 作为主车到辅车的正式通信链路

    @return 已初始化至配置波特率的 UART8 对象
    """
    uart8 = UART(UART8_PORT_ID)
    uart8.init(UART_BAUDRATE)
    return uart8


def create_uart6():
    """@brief 创建并初始化 UART6

    UART6 是本车本地视觉链路

    @return 已初始化至配置波特率的 UART6 对象
    """
    uart6 = UART(UART6_PORT_ID)
    uart6.init(UART_BAUDRATE)
    return uart6
