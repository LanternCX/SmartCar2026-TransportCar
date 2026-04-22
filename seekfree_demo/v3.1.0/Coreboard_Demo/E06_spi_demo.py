# 本示例程序演示如何使用 machine 库的 SPI 类接口
# 使用 RT1021-MicroPython 核心板
# 可以用杜邦线将 MOSI 与 MISO 短接测试 也可以接入传感器

# 示例程序运行效果为每 500ms(0.5s) 改变一次 RT1021-MicroPython 核心板的 LED 亮灭状态
# 并通过对应引脚进行 SPI 数据传输
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
#   构造接口 标准 MicroPython 的 machine.SPI 模块
#   SPI_obj = SPI(id)
#       id              接口编号    |   必要参数 本固件支持 [0, 3] 总共 4 个 SPI 模块
#       return          返回内容    |   正常情况下返回对应 SPI 的对象
# ------------------------------------------------------------------------------
# 接口编号与对应 ID 和 引脚 对应表 请对照下表查找各自板子支持的引脚
# 需要注意的是 RT1021-144P-BTB  核心板 LPSPI1 不能使用
# 需要注意的是 RT1021-100P-2.54 核心板 LPSPI2 不能使用
# ---------------------------------------------------------------------------------------------------------
# |     Board Type    |          144P-BTB         |         144P-2.54         |         100P-2.54         |
# |-------------------|---------------------------|---------------------------|---------------------------|
# | HW-SPI  | Logical | SCK  | MOSI | MISO | CS0  | SCK  | MOSI | MISO | CS0  | SCK  | MOSI | MISO | CS0  |
# |-------------------|---------------------------|---------------------------|---------------------------|
# | LPSPI1  | id = 0  |      |      |      |      | B10  | B12  | B13  | B11  | B10  | B12  | B13  | B11  |
# | LPSPI2  | id = 1  | C10  | C12  | C13  | C11  | C10  | C12  | C13  | C11  |      |      |      |      |
# | LPSPI3  | id = 2  | B28  | B30  | B31  | B29  | B28  | B30  | B31  | B29  | B28  | B30  | B31  | B29  |
# | LPSPI4  | id = 3  | B18  | B20  | B21  | B19  | B18  | B20  | B21  | B19  | D0   | D2   | D3   | D1   |
# ---------------------------------------------------------------------------------------------------------
SPI_SELECT = None
if BOARD_TYPE == 'RT1021_144P_BTB':
    SPI_SELECT = 1      # Select LPSPI2 Input id = 1
elif BOARD_TYPE == 'RT1021_144P_2P54':
    SPI_SELECT = 1      # Select LPSPI2 Input id = 1
elif BOARD_TYPE == 'RT1021_100P_2P54':
    SPI_SELECT = 0      # Select LPSPI1 Input id = 0
spi = SPI(SPI_SELECT)  # pyright: ignore[reportArgumentType]

# SPI 接口 :
# ------------------------------------------------------------------------------
#   SPI 参数设置 参数说明
#   SPI.init(baudrate = 1000000, polarity = 0, phase = 0)
#       baudrate        传输速率    |   默认 1000000 1Mbps
#       polarity        电平极性    |   可选参数 默认 0 {0 - 时钟空闲时低电平, 1 - 时钟空闲时高电平}
#       phase           时钟相位    |   可选参数 默认 0 {0 - 第一个时钟沿采样数据, 1 - 第二个时钟沿采样数据}
# ------------------------------------------------------------------------------
#   读取指定的字节数 同时连续发送指定的单个字节 默认发送 0x00
#   rx_buff = spi.read(lenght, wite = 0)
#       lenght          读取长度    |   必要参数 准备读取的数据长度
#       wite            发送数据    |   可选参数 默认为 0x00
#       return          返回内容    |   返回读取到的内容 为字节数组形式
# ------------------------------------------------------------------------------
#   读取 rx_buff 长度数据 同时连续发送指定的单个字节 默认发送 0x00
#   spi.readinto(rx_buff, wite = 0)
#       rx_buff         数据缓冲    |   必要参数 存放读取数据的缓冲区
#       wite            发送数据    |   可选参数 默认为 0x00
# ------------------------------------------------------------------------------
#   发送 tx_buff 长度数据
#   spi.write(tx_buff)
#       tx_buff         数据缓冲    |   必要参数 存放发送数据的缓冲区
# ------------------------------------------------------------------------------
#   发送 tx_buff 长度数据 同时读取数据到 rx_buff 这两个缓冲区必须一样长
#   spi.write_readinto(tx_buff, rx_buff)
#       rx_buff         数据缓冲    |   必要参数 存放读取数据的缓冲区
#       tx_buff         数据缓冲    |   必要参数 存放发送数据的缓冲区
# ------------------------------------------------------------------------------

spi.init(baudrate = 1000000, polarity = 0, phase = 0)

tx_buff = bytearray(b'1234')
rx_buff = bytearray(len(tx_buff))

while True:
    # 每 500ms 读取一次 将数据再原样发回
    time.sleep_ms(500)
    # 翻转 C4 LED 电平
    led.toggle()

    rx_byte = spi.read(1)
    spi.readinto(rx_buff)
    spi.write(tx_buff)
    spi.write_readinto(tx_buff, rx_buff)

    # 把 MOSI 和 MISO 接到一起可以看到发送输入是一样的数据
    print("write_readinto out:", tx_buff)
    print("write_readinto in :", rx_buff)
    
    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()
