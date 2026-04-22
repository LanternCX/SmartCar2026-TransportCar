# 本示例程序演示如何使用 machine 库的 UART 类接口
# 使用 RT1021-MicroPython 核心板
# 搭配 USB 转 TTL 模块进行 UART 通信测试

# 示例程序运行效果为每 500ms(0.5s) 改变一次 RT1021-MicroPython 核心板的 LED 亮灭状态
# 并通过 UART 接收并回传数据
# 当 SWITCH2 引脚电平出现变化时退出测试程序

# 包含 gc 与 time 类
import gc, time
# 从 machine 库包含所有内容
from machine import *
# 从 seekfree 库包含所有内容
from seekfree import *

# 延迟上电 避免 CR 时序控制导致屏幕还未成功启动
time.sleep_ms(100)

print("REAL TYPE : " + BOARD_TYPE)
print("BOARD VERSION : " + BOARD_VERSION)

LED_PIN = 'C4'
SWITCH2_PIN = None
if BOARD_TYPE == 'RT1021_144P_BTB':
    # RT1021-144P-BTB 核心板上 C4  是 LED
    # RT1021-144P-BTB 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
elif BOARD_TYPE == 'RT1021_144P_2P54':
    # RT1021-144P-2.54 核心板上 C4  是 LED
    # RT1021-144P-2.54 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
elif BOARD_TYPE == 'RT1021_100P_2P54':
    # RT1021-100P-2.54 核心板上 C4  是 LED
    # RT1021-100P-2.54 学习板上 C19 对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'C19'

print("LED_PIN     : " + LED_PIN)
print("SWITCH2_PIN : " + SWITCH2_PIN)  # pyright: ignore[reportOperatorIssue]

led     = Pin(LED_PIN, Pin.OUT, value = True)
switch2 = Pin(SWITCH2_PIN, Pin.IN , pull = Pin.PULL_UP_47K)  # pyright: ignore[reportArgumentType]
state2  = switch2.value()

# ------------------------------------------------------------------------------
#   构造接口 标准 MicroPython 的 machine.UART 模块
#   UART_obj = UART(id)
#       id              接口编号    |   必要参数 本固件支持 [0, 7] 总共 8 个 UART 模块
#       return          返回内容    |   正常情况下返回对应 UART 的对象
# ------------------------------------------------------------------------------
# 接口编号与对应 ID 和 引脚 对应表 请对照下表查找各自板子支持的引脚
# 需要注意的是 RT1021-144P-BTB 核心板 LPUART5 / LPUART7 不能使用
# ------------------------------------------------------------
# |     Board Type    |  144P-BTB  | 144P-2.54  | 100P-2.54  |
# |-------------------|------------|------------|------------|
# | HW-UART | Logical | TX   | RX  | TX   | RX  | TX   | RX  |
# |-------------------|------------|------------|------------|
# | LPUART1 | id = 0  | B6   | B7  | B6   | B7  | B6   | B7  |
# | LPUART2 | id = 1  | C22  | C23 | C22  | C23 | C22  | C23 |
# | LPUART3 | id = 2  | C6   | C7  | C6   | C7  | C6   | C7  |
# | LPUART4 | id = 3  | D0   | D1  | D0   | D1  | B26  | B27 |
# | LPUART5 | id = 4  |      |     | B10  | B11 | B10  | B11 |
# | LPUART6 | id = 5  | D20  | D21 | D20  | D21 | D20  | D21 |
# | LPUART7 | id = 6  |      |     | D17  | D18 | D2   | D3  |
# | LPUART8 | id = 7  | D22  | D23 | D22  | D23 | D22  | D23 |
# ------------------------------------------------------------
uart3 = UART(2)     # Select LPUART3 Input id = 2

# UART 接口 :
# ------------------------------------------------------------------------------
#   串口参数设置
#   UART.init(baudrate = 9600, bits = 8, parity = None, stop = 1, ...)
#       baudrate        串口速率    |   必要参数 默认 9600
#       bits            数据位数    |   可选参数 默认 8 bits 数据位
#       parity          校验位数    |   可选参数 默认 None (None, 0, 1) 无校验, 偶校验, 奇校验
#       stop            停止位数    |   可选参数 默认 1 bit 停止位
# ------------------------------------------------------------------------------
#   将 bufffer 内容通过 UART 发送
#   UART.write(bufffer)
#       bufffer         数据缓冲    |   必要参数 存放发送数据的缓冲区
# ------------------------------------------------------------------------------
#   查询 UART 是否有数据可读取 返回可读取长度
#   lenght = UART.any()
#       return          返回内容    |   返回缓冲区内数据长度 字节单位
# ------------------------------------------------------------------------------
#   读取 lenght 字节到 bufffer
#   bufffer = UART.read(lenght)
#       lenght          读取长度    |   必要参数 准备读取的数据长度
#       return          返回内容    |   返回读取到的内容 为字节数组形式
# ------------------------------------------------------------------------------

uart3.init(460800)
uart3.write("Test.\r\n")
buf_len = 0

while True:
    # 每 500ms 读取一次 将数据再原样发回
    time.sleep_ms(500)
    # 翻转 C4 LED 电平
    led .toggle()
    
    buf_len = uart3.any()
    if(buf_len):
        buf = uart3.read(buf_len)
        print("uart3 buf_len = %6d"%(buf_len))
        print("uart3 buf_data = %s"%(buf))
        uart3.write("uart3:")
        uart3.write(buf)

    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()
