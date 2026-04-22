# 本示例程序演示如何使用 machine 库的 ADC 类接口
# 使用 RT1021-MicroPython 核心板
# 搭配对应拓展学习板的电池电压检测电路

# 示例程序运行效果为每 100ms(0.1s) 改变一次 RT1021-MicroPython 核心板的 LED 亮灭状态
# 并通过 RT1021-MicroPython 核心板的 Type-C 的 CDC 虚拟串口输出一次转换数据结果
#   (如果是 RT1021-144P-BTB 核心板 或者 RT1021-144P-2.54 核心板 则输出以下两句)
#       ADC value = xxxx, power voltage = xx.xxV.
#       inductor1_adc = xxxx.
#   (如果是 RT1021-100P-2.54 核心板 则只输出一句)
#       inductor1_adc = xxxx.
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
POWER_ADC_PIN = None
INDUCTOR1_ADC_PIN = None
if BOARD_TYPE == 'RT1021_144P_BTB':
    # RT1021-144P-BTB 核心板上 C4  是 LED
    # RT1021-144P-BTB 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 B27 对应电源电压检测
    # RT1021-144P-BTB 学习板上 B12 对应一号电感运放输入
    POWER_ADC_PIN = 'B27'
    INDUCTOR1_ADC_PIN = 'B12'
elif BOARD_TYPE == 'RT1021_144P_2P54':
    # RT1021-144P-2.54 核心板上 C4  是 LED
    # RT1021-144P-2.54 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-2.54 学习板上 B27 对应电源电压检测
    # RT1021-144P-2.54 学习板上 B12 对应一号电感运放输入
    POWER_ADC_PIN = 'B27'
    INDUCTOR1_ADC_PIN = 'B12'
elif BOARD_TYPE == 'RT1021_100P_2P54':
    # RT1021-100P-2.54 核心板上 C4  是 LED
    # RT1021-100P-2.54 学习板上 C19 对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'C19'
    # RT1021-100P-2.54 学习板上 没有电源电压检测
    # RT1021-100P-2.54 学习板上 B14 对应一号电感运放输入
    INDUCTOR1_ADC_PIN = 'B14'

print("LED_PIN     : " + LED_PIN)
print("SWITCH2_PIN : " + SWITCH2_PIN)  # pyright: ignore[reportOperatorIssue]
print("POWER_ADC_PIN : " + ((POWER_ADC_PIN)if(None != POWER_ADC_PIN)else("N/A")))  # pyright: ignore[reportOperatorIssue]
print("INDUCTOR1_ADC_PIN : " + INDUCTOR1_ADC_PIN)  # pyright: ignore[reportOperatorIssue]

led     = Pin(LED_PIN, Pin.OUT, value = True)
switch2 = Pin(SWITCH2_PIN, Pin.IN , pull = Pin.PULL_UP_47K)  # pyright: ignore[reportArgumentType]
state2  = switch2.value()

# ------------------------------------------------------------------------------
#   构造接口 是标准 MicroPython 的 machine.ADC 模块
#   ADC_obj = ADC(pin)
#       pin             引脚名称    |   必要参数 引脚名称 本固件以核心板上引脚编号为准
#       return          返回内容    |   正常情况下返回对应 ADC 通道的对象
# ------------------------------------------------------------------------------
if(None != POWER_ADC_PIN):
    power_adc = ADC(POWER_ADC_PIN)  # pyright: ignore[reportArgumentType]
inductor1_adc = ADC(INDUCTOR1_ADC_PIN)  # pyright: ignore[reportArgumentType]

# ADC 接口 :
# ------------------------------------------------------------------------------
#   读取当前端口的 ADC 转换值
#   ADC.read_u16()
#       return          返回内容    |   ADC 转换数值 数据返回范围是 [0, 65535]
# ------------------------------------------------------------------------------

while True:
    # 延时 100 ms
    time.sleep_ms(100)
    # 翻转 C4 LED 电平
    led.toggle()
    
    if(None != POWER_ADC_PIN):
        power_adc_value = power_adc.read_u16()
        # 学习板上分压电路为 1/(1 + 10) 参考电压 3.3V
        # 因此换算公式为 power_adc_value / 65535 * 3.3 * 11 = power_voltage (V)
        print("ADC value = {:>6d}, power voltage = {:>2.2f}V.".format(
            power_adc_value,
            power_adc_value / 65535 * 3.3 * 11))
    # 读取通过 read_u16 接口读取 无参数 数据返回范围是 0-65535
    print("inductor1_adc = {:>6d}.".format(inductor1_adc.read_u16()))
    
    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()
