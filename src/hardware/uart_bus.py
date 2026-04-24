"""UART 总线初始化封装

提供三条 UART 总线的工厂函数, 分别服务于控制命令、主辅车通信和视觉输入
"""

from machine import UART


def create_uart3():
    """@brief 创建并初始化 UART3

    UART3 承担上游控制命令与查询回包的传输职责, 固定波特率 115200

    @return 已初始化至 115200 bps 的 UART(2) 对象
    """
    uart3 = UART(2)
    uart3.init(115200)
    return uart3


def create_uart8():
    """@brief 创建并初始化 UART8

    UART8 作为主车到辅车的正式通信链路, 固定波特率 115200

    @return 已初始化至 115200 bps 的 UART(7) 对象
    """
    uart8 = UART(7)
    uart8.init(115200)
    return uart8


def create_uart6():
    """@brief 创建并初始化 UART6

    UART6 负责辅车本地视觉输入的数据接收, 固定波特率 115200

    @return 已初始化至 115200 bps 的 UART(5) 对象
    """
    uart6 = UART(5)
    uart6.init(115200)
    return uart6
