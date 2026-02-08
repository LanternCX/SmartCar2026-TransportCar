"""UART 初始化封装"""
from machine import UART


def create_uart3():
    uart3 = UART(2)
    uart3.init(115200)
    return uart3


def create_uart6():
    uart6 = UART(5)
    uart6.init(115200)
    return uart6
