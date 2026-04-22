# 本示例程序演示如何使用 smartcar 库的 ADC_Group 类接口
# 使用 RT1021-MicroPython 核心板搭配对应拓展学习板的四路电磁运放接口

# 示例程序运行效果为每 200ms(0.2s) LED 改变亮灭状态
# 并通过 Type-C 的 CDC 虚拟串口输出一次信息
# 当 SWITCH2 引脚电平出现变化时退出测试程序

# ADC_Group 的采集周期计算方式
# Ticker 通过 start(y) 启动时 y 代表 Ticker 的周期
# 此时每 y 毫秒会触发一次 ADC_Group 的更新
# 因此 ADC_Group 的采集周期时间等于 y 本例程中就是 10ms

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
ADC_GROUP_CHANNLE1 = None
ADC_GROUP_CHANNLE2 = None
if BOARD_TYPE == 'RT1021_144P_BTB':
    # RT1021-144P-BTB 核心板上 C4  是 LED
    # RT1021-144P-BTB 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 B14 是电感运放通道二
    # RT1021-144P-BTB 学习板上 B15 是电感运放通道三
    ADC_GROUP_CHANNLE1 = 'B14'
    ADC_GROUP_CHANNLE2 = 'B15'
elif BOARD_TYPE == 'RT1021_144P_2P54':
    # RT1021-144P-2.54 核心板上 C4  是 LED
    # RT1021-144P-2.54 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 B14 是电感运放通道二
    # RT1021-144P-BTB 学习板上 B15 是电感运放通道三
    ADC_GROUP_CHANNLE1 = 'B14'
    ADC_GROUP_CHANNLE2 = 'B15'
elif BOARD_TYPE == 'RT1021_100P_2P54':
    # RT1021-100P-2.54 核心板上 C4  是 LED
    # RT1021-100P-2.54 学习板上 C19 对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'C19'
    # RT1021-144P-BTB 学习板上 B14 是电感运放通道一
    # RT1021-144P-BTB 学习板上 B15 是电感运放通道二
    ADC_GROUP_CHANNLE1 = 'B14'
    ADC_GROUP_CHANNLE2 = 'B15'

print("LED_PIN     : " + LED_PIN)
print("SWITCH2_PIN : " + SWITCH2_PIN)  # pyright: ignore[reportOperatorIssue]
print("ADC_GROUP_CHANNLE1 : " + ADC_GROUP_CHANNLE1)  # pyright: ignore[reportOperatorIssue]
print("ADC_GROUP_CHANNLE2 : " + ADC_GROUP_CHANNLE2)  # pyright: ignore[reportOperatorIssue]

led     = Pin(LED_PIN, Pin.OUT, value = True)
switch2 = Pin(SWITCH2_PIN, Pin.IN , pull = Pin.PULL_UP_47K)  # pyright: ignore[reportArgumentType]
state2  = switch2.value()

# ------------------------------------------------------------------------------
#   构造接口 用于构建一个 ADC_Group 对象
#   ADC_Group_obj = ADC_Group(id)
#       id              模块索引    |   必要参数 RT1021 对应有 [1,2] 总共两个模块可选
#       return          返回内容    |   正常情况下返回对应 ADC_Group 的对象
# ------------------------------------------------------------------------------
adc_group = ADC_Group(1)

# ADC_Group 接口 :
# ------------------------------------------------------------------------------
#   ADC_Group 添加对应引脚 需要该引脚是对应 ADC 模块的通道引脚
#   ADC_Group.addch(pin_name)
#       pin_name        引脚名称    |   必要参数 引脚名称 本固件以核心板上引脚编号为准
# ------------------------------------------------------------------------------
#   直接调用的初始化接口 用于初始化制定的 ADC 硬件 需要注意本方法只能直接 ADC_Group.init 调用
#    ADC_Group.init(period = ADC_Group.PMODE3, average = ADC_Group.AVG16)
#       id              模块索引    |   必要参数 RT1021 对应有 [1, 2] 总共两个模块可选
#       period          采样周期    |   可选参数 关键字输入 默认 ADC_Group.x, x = {PMODE0, PMODE1, PMODE2, PMODE3}
#       average         均值选项    |   可选参数 关键字输入 默认 ADC_Group.x, x = {AVG1, AVG4, AVG8, AVG16, AVG32}
# ------------------------------------------------------------------------------
#   触发一次 ADC_Group 的转换 结果更新到数据缓冲区
#   ADC_Group.capture()
# ------------------------------------------------------------------------------
#   从 ADC_Group 数据缓冲区获取最新的数据
#   data_buffer = ADC_Group.get()
#       return          返回内容    |   返回当前 ADC_Group 的转换数值 为一个列表
# ------------------------------------------------------------------------------
#   触发一次 capture 方法接口 并从 ADC_Group 数据缓冲区获取最新的数据
#   data_buffer = ADC_Group.read()
#       return          返回内容    |   返回当前 ADC_Group 的转换数值 为一个列表
# ------------------------------------------------------------------------------

# 将通道添加进来
adc_group.addch(ADC_GROUP_CHANNLE1)  # pyright: ignore[reportArgumentType]
adc_group.addch(ADC_GROUP_CHANNLE2)  # pyright: ignore[reportArgumentType]

ticker_flag = False
ticker_count = 0

# 定义一个回调函数 必须有一个参数用于传递实例本身 这个参数就是 ticker 实例自身
def time_pit_handler (ticker_obj):
    # 需要注意的是这里得使用 global 修饰全局属性
    # 否则它会新建一个局部变量
    global ticker_flag, ticker_count
    ticker_flag = True
    ticker_count = (ticker_count + 1) if (ticker_count < 100) else (1)

pit1 = ticker(1)
pit1.capture_list(adc_group)
pit1.callback(time_pit_handler)
pit1.start(10)

while True:
    if (ticker_flag and ticker_count % 20 == 0):
        led.toggle()
        # Tips : 通过 capture 接口更新数据 但在这个例程中被 ticker.capture_list 模块接管了
        # adc_group.capture()

        # 通过 get 接口获取数据 数据返回范围是 0-4095
        adc_data = adc_group.get()
        print("adc={:>6d},{:>6d}.\r\n".format(
            adc_data[0], adc_data[1]))
        ticker_flag = False

    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        pit1.stop()
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()
