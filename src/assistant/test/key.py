"""辅车按键电平测试脚本.

@file src/assistant/test/key.py

本脚本用于测试辅车的四个按键引脚（C8, C9, C14, C15）的电平读数。

运行效果：
- 每 100ms 读取一次四个按键引脚的电平状态
- 输出格式：C8=x C9=x C14=x C15=x
- 当 D9 引脚电平变化时退出程序
"""

from machine import Pin
import gc
import time

# 延迟上电，避免时序问题
time.sleep_ms(100)

# 核心板 C4 LED 用于指示程序运行
led = Pin("C4", Pin.OUT, value=True)

# D9 拨码开关用于退出程序
switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
state2 = switch2.value()

# 构造四个按键的 Pin 对象
# C8, C9, C14, C15 是辅车的四个按键引脚
key_c8 = Pin("C8", Pin.IN, pull=Pin.PULL_UP_47K)
key_c9 = Pin("C9", Pin.IN, pull=Pin.PULL_UP_47K)
key_c14 = Pin("C14", Pin.IN, pull=Pin.PULL_UP_47K)
key_c15 = Pin("C15", Pin.IN, pull=Pin.PULL_UP_47K)

print("辅车按键电平测试开始")
print("按键引脚: C8, C9, C14, C15")
print("当 D9 拨码开关状态改变时退出程序")
print("-" * 60)

while True:
    # 延时 100ms
    time.sleep_ms(100)

    # 翻转 LED 指示程序运行
    led.toggle()

    # 读取四个按键的电平值（0 或 1）
    c8_value = key_c8.value()
    c9_value = key_c9.value()
    c14_value = key_c14.value()
    c15_value = key_c15.value()

    # 输出电平状态
    print(
        "C8={:>1d}  C9={:>1d}  C14={:>1d}  C15={:>1d}".format(
            c8_value, c9_value, c14_value, c15_value
        )
    )

    # 如果 D9 拨码开关状态改变，退出程序
    if switch2.value() != state2:
        print("-" * 60)
        print("检测到 D9 拨码开关状态改变，程序退出")
        break

    # 回收内存
    gc.collect()

print("辅车按键电平测试结束")
