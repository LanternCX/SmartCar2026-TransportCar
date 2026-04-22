# 本示例程序演示如何使用 seekfree 库的 BLDC_CONTROLLER 类接口
# 使用 RT1021-MicroPython 核心板搭配 STC 无刷电调测试

# 示例程序运行效果为按一次 KEY4 按键后启动
# 随后无刷电机加减速转动
# LED 会不间断闪烁
# 当 SWITCH2 引脚电平出现变化时退出测试程序

# 包含 gc 与 time 类
import gc, time
# 从 machine 库包含所有内容
from machine import *
# 从 smartcar 库包含所有内容
from smartcar import *
# 从 seekfree 库包含所有内容
from seekfree import *

# 延迟上电 避免 CR 时序控制导致屏幕还未成功启动
time.sleep_ms(100)

print("REAL TYPE : " + BOARD_TYPE)
print("BOARD VERSION : " + BOARD_VERSION)

LED_PIN = 'C4'
SWITCH2_PIN = None
KEY4_PIN = None
BLDC_CONTROLLER1_SELECT = None
BLDC_CONTROLLER2_SELECT = None
if BOARD_TYPE == 'RT1021_144P_BTB':
    # RT1021-144P-BTB 核心板上 C4  是 LED
    # RT1021-144P-BTB 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 C15 对应四号按键
    KEY4_PIN = 'C15'
    BLDC_CONTROLLER1_SELECT = BLDC_CONTROLLER.PWM_C25
    BLDC_CONTROLLER2_SELECT = BLDC_CONTROLLER.PWM_C27
elif BOARD_TYPE == 'RT1021_144P_2P54':
    # RT1021-144P-2.54 核心板上 C4  是 LED
    # RT1021-144P-2.54 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 C15 对应四号按键
    KEY4_PIN = 'C15'
    BLDC_CONTROLLER1_SELECT = BLDC_CONTROLLER.PWM_C25
    BLDC_CONTROLLER2_SELECT = BLDC_CONTROLLER.PWM_C27
elif BOARD_TYPE == 'RT1021_100P_2P54':
    # RT1021-100P-2.54 核心板上 C4  是 LED
    # RT1021-100P-2.54 学习板上 C19 对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'C19'
    # RT1021-144P-BTB 学习板上 D23 对应四号按键
    KEY4_PIN = 'D23'
    BLDC_CONTROLLER1_SELECT = BLDC_CONTROLLER.PWM_B26
    BLDC_CONTROLLER2_SELECT = BLDC_CONTROLLER.PWM_B27

print("LED_PIN     : " + LED_PIN)
print("SWITCH2_PIN : " + SWITCH2_PIN)  # pyright: ignore[reportOperatorIssue]
print("KEY4_PIN    : " + KEY4_PIN)  # pyright: ignore[reportOperatorIssue]

led     = Pin(LED_PIN, Pin.OUT, value = True)
switch2 = Pin(SWITCH2_PIN, Pin.IN , pull = Pin.PULL_UP_47K)  # pyright: ignore[reportArgumentType]
key4    = Pin(KEY4_PIN, Pin.IN , pull = Pin.PULL_UP_47K)  # pyright: ignore[reportArgumentType]
state2  = switch2.value()

# 显示帮助信息
BLDC_CONTROLLER.help()
time.sleep_ms(500)

# 初始 1.1ms 高电平 确保能够起转
high_level_us = 1100
# 动作方向
dir = 1

# C24 与 C25 属于同一个PWM子模块
# C26 与 C27 属于同一个PWM子模块
# 因此使用时他们不能冲突
# 建议使用无刷电调时不使用 C25 / C27 的PWM功能
# 电调一般起转需要在 1.1ms 高电平时间比较保险
# 因为 电机各不一样 会有一些死区差异 同时安装后有负载差异

# ------------------------------------------------------------------------------
#   构造接口 用于构建一个 BLDC_CONTROLLER 对象
#   BLDC_CONTROLLER(index,[freq, highlevel_us])
#       index           接口索引    |   必要参数 数值范围查看固件说明书 或者通过 BLDC_CONTROLLER.help() 查看
#       freq            信号频率    |   可选参数 关键字参数 PWM 频率 范围 50-300 默认 50
#       highlevel_us    高电平值    |   可选参数 关键字参数 初始的高电平时长 范围 [1000-2000] 默认 1000
# ------------------------------------------------------------------------------
bldc1 = BLDC_CONTROLLER(BLDC_CONTROLLER1_SELECT, freq=300, highlevel_us = 1000)  # pyright: ignore[reportArgumentType]
bldc2 = BLDC_CONTROLLER(BLDC_CONTROLLER2_SELECT, freq=300, highlevel_us = 1000)  # pyright: ignore[reportArgumentType]

# BLDC_CONTROLLER 接口 :
# ------------------------------------------------------------------------------
#   更新或获取高电平时间值
#   BLDC_CONTROLLER.highlevel_us([highlevel_us])
#       highlevel_us    高电平值    |   可选参数 填数值就设置新的高电平时长 否则返回当前高电平时长 范围是 [1000-2000]
# ------------------------------------------------------------------------------
#   可以直接通过类调用 也可以通过对象调用 输出模块的使用帮助信息
#   BLDC_CONTROLLER.help()
# ------------------------------------------------------------------------------
#   通过对象调用 输出当前对象的自身信息
#   BLDC_CONTROLLER.info()
# ------------------------------------------------------------------------------

bldc1.info()
bldc2.info()
time.sleep_ms(500)

# 需要按一次按键启动
print("Wait for KEY-%s to be pressed.\r\n"%KEY4_PIN)
while True:
    time.sleep_ms(100)
    led.toggle()
    if 0 == key4.value():
        print("BLDC Controller test running.\r\n")
        print("Press KEY-%s to suspend the program.\r\n"%KEY4_PIN)
        time.sleep_ms(300)
        break

while True:
    time.sleep_ms(100)
    led.toggle()
    # 往复计算 BLDC 电调速度
    if dir:
        high_level_us = high_level_us + 5
        if high_level_us >= 1250:
            dir = 0
    else:
        high_level_us = high_level_us - 5
        if high_level_us <= 1100:
            dir = 1
    
    # 设置更新高电平时间输出
    print("Set BLDC HIGHLEVEL Us to {:>6d}.".format(high_level_us))
    bldc1.highlevel_us(high_level_us)
    bldc2.highlevel_us(high_level_us)
    
    if 0 == key4.value():
        print("Suspend.\r\n")
        print("Wait for KEY-%s to be pressed.\r\n"%KEY4_PIN)
        bldc1.highlevel_us(1000)
        bldc2.highlevel_us(1000)
        time.sleep_ms(300)
        while True:
            if 0 == key4.value():
                print("BLDC Controller test running.\r\n")
                print("Press KEY-%s to suspend the program.\r\n"%KEY4_PIN)
                high_level_us = 1100
                dir = 1
                time.sleep_ms(300)
                break
    
    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()
