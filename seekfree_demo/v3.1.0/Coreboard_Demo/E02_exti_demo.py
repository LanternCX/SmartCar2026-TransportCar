
# 本示例程序演示如何使用 machine 库的 Pin 类接口的外部中断
# 使用 RT1021-MicroPython 核心板搭配对应拓展学习板的按键

# 示例程序运行效果为每 50ms 改变一次 RT1021-MicroPython 核心板的 LED 亮灭状态
# 当 KEY1 引脚电平出现由高拉低的下降沿时(也就是按下时) 触发一次外部中断回调
# 中断回调通过 RT1021-MicroPython 核心板的 Type-C 的 CDC 虚拟串口输出触发次数
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
KEY1_PIN = None
if BOARD_TYPE == 'RT1021_144P_BTB':
    # RT1021-144P-BTB 核心板上 C4  是 LED
    # RT1021-144P-BTB 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 C8  对应一号按键
    KEY1_PIN = 'C8'
elif BOARD_TYPE == 'RT1021_144P_2P54':
    # RT1021-144P-2.54 核心板上 C4  是 LED
    # RT1021-144P-2.54 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-2.54 学习板上 C8  对应一号按键
    KEY1_PIN = 'C8'
elif BOARD_TYPE == 'RT1021_100P_2P54':
    # RT1021-100P-2.54 核心板上 C4  是 LED
    # RT1021-100P-2.54 学习板上 C19 对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'C19'
    # RT1021-100P-2.54 学习板上 D20 对应一号按键
    KEY1_PIN = 'D20'

print("LED_PIN     : " + LED_PIN)
print("SWITCH2_PIN : " + SWITCH2_PIN)
print("KEY1_PIN    : " + KEY1_PIN)

led     = Pin(LED_PIN, Pin.OUT, value = True)
switch2 = Pin(SWITCH2_PIN, Pin.IN , pull = Pin.PULL_UP_47K)
key1    = Pin(KEY1_PIN, Pin.IN , pull = Pin.PULL_UP_47K)
state2  = switch2.value()

# 新建变量用于 标识 计数 状态保存
key_exti_flag  = False
key_exti_count = 0
key_exti_state = 0

# 定义一个回调函数 必须有一个参数用于传递实例本身 这个参数就是触发外部中断的 Pin 实例自身
def key_exti_handler (pin_obj):
    # global 是全局变量修饰 说明这里使用的是一个全局变量
    # 否则函数会新建一个临时变量
    global key_exti_flag, key_exti_count, key_exti_state

    # 标识置位 计数递增 并获取当前中断触发引脚的电平状态
    # 由于该引脚上并没有滤波消抖电路 所以读取电平与触发信号可能不对应
    key_exti_flag  = True
    key_exti_count = key_exti_count + 1
    key_exti_state = pin_obj.value()

# ------------------------------------------------------------------------------
#   配置 Pin 的中断 也就是外部中断 EXTI
#   Pin.irq(handler, trigger, hard)
#       handler         回调函数    |   必要参数 触发后对应的回调函数 python 函数
#       trigger         触发模式    |   必要参数 可用值为 Pin.x, x = (IRQ_RISING, IRQ_FALLING)
#       hard            应用模式    |   可选参数 可用值为 False True
# ------------------------------------------------------------------------------
key1.irq(key_exti_handler, Pin.IRQ_FALLING, False)

while True:
    time.sleep_ms(50)
    led.toggle()

    # 标识置位后 清空标识 并通过 Type-C 的 CDC 虚拟串口输出触发次数
    if key_exti_flag:
        key_exti_flag = False
        print("key_exti_count = %6d, key_exti_state = %1d"%(key_exti_count, key_exti_state))
    
    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()
