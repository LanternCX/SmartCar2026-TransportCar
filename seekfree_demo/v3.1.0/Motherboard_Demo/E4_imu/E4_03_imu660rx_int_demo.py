# 本示例程序演示如何使用 seekfree 库的 IMU660RX 类接口
# 使用 RT1021-MicroPython 核心板搭配对应拓展学习板与 IMU660RX 模块测试

# 示例程序运行效果为每 200ms(0.2s) 通过 Type-C 的 CDC 虚拟串口输出信息
# 当 SWITCH2 引脚电平出现变化时退出测试程序
# 如果看到 Thonny Shell 控制台输出 ValueError: Module init fault. 报错
# 就证明 IMU660RX 模块连接异常 或者模块型号不对 或者模块损坏
# 请检查模块型号是否正确 接线是否正常 线路是否导通 无法解决时请联系技术支持

# IMU660RX 使能硬件解算时 必须要连接 INT2 引脚
# 随后固件会自动通过 INT2 硬件触发外部中断进行全自动解算
# 不再需要 Ticker 来触发软件采集
# 数据更新频率参照设置的硬解频率

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

# 显示帮助信息
# 帮助信息中会显示支持那些模块
# 以及具体的 刷新频率 / 量程范围
IMU660RX.help()

# ------------------------------------------------------------------------------
#   构造接口 用于构建一个 IMU660RX 对象
#   IMU660RX_obj = IMU660RX(capture_div = 1, imu_type = IMU660RX.TYPE_RA, quar_rate = IMU660RX.RATE_DISABLE)
#       capture_div     采集分频    |   可选关键字参数 默认为 1 也就是每次都采集 代表多少次触发进行一次采集
#       imu_type        模块型号    |   可选关键字参数 IMU660RX.TYPE_x, x = (AUTO, RA, RB, RC) 默认 AUTO
#       quar_rate       硬解频率    |   可选关键字参数 IMU660RX.RATE_x, x = (15HZ, 30HZ, 60HZ, 120HZ, 240HZ, 480HZ, DISABLE) 默认 DISABLE
#       return          返回内容    |   正常情况下返回对应 IMU660RX 的对象
# ------------------------------------------------------------------------------
imu = IMU660RX(imu_type = IMU660RX.TYPE_RC, quar_rate = IMU660RX.RATE_120HZ)

# IMU660RX 接口 :
# ------------------------------------------------------------------------------
#   增加一个 IMU 的采集请求 当达到 capture_div 数量时进行一次采集并将数据缓存
#   IMU660RX.capture()
# ------------------------------------------------------------------------------
#   从 IMU 对象获取 原始数据缓冲区
#   data_list = IMU660RX.get()
#       return          返回内容    |   返回 IMU 原始数据缓冲区 返回为一个列表
# ------------------------------------------------------------------------------
#   从 IMU 对象获取 欧拉角数据缓冲区
#   data_list = IMU660RX.get_euler()
#       return          返回内容    |   返回 IMU 欧拉角数据缓冲区 返回为一个列表
# ------------------------------------------------------------------------------
#   从 IMU 对象获取 四元数数据缓冲区
#   data_list = IMU660RX.get_quarternion()
#       return          返回内容    |   返回 IMU 四元数数据缓冲区 返回为一个列表
# ------------------------------------------------------------------------------
#   立即进行一次 capture 并从 IMU 数据缓冲区获取最新的数据
#   data_list = IMU660RX.read()
#       return          返回内容    |   返回当前 IMU 原始数据缓冲区 返回为一个列表
# ------------------------------------------------------------------------------
#   获取当前的采集分频
#   capture_div = IMU660RX.get_capture_div()
#       return          返回内容    |   返回当前 IMU 当前的采集分频
# ------------------------------------------------------------------------------
#   可以直接通过类调用 也可以通过对象调用 输出模块的使用帮助信息
#   IMU660RX.help()
# ------------------------------------------------------------------------------
#   通过对象调用 输出当前对象的自身信息
#   IMU660RX.info()
# ------------------------------------------------------------------------------

imu.info()

# 通过 get 接口读取数据
# 本质上是将 Python 对象与传感器数据缓冲区链接起来
# 所以只需要一次 IMU660RX.get() 后就不需要再调用这个接口
# 之后直接使用获取的列表对象即可 它的数据会随 caputer 更新
imu_raw_data   = imu.get()
imu_euler_data = imu.get_euler()
imu_quar_data  = imu.get_quarternion()

while True:
    # 延时 100 ms
    time.sleep_ms(100)
    # Tips : RC 启用硬解后 必须接 INT2 引脚 它会自动触发外部中断解算

    # 翻转 LED 电平
    led.toggle()
    print("acc   = {:>6d}, {:>6d}, {:>6d}.Sequence (acc_x, acc_y, acc_z).".format(imu_raw_data[0], imu_raw_data[1], imu_raw_data[2]))
    print("gyro  = {:>6d}, {:>6d}, {:>6d}.Sequence (gyro_x, gyro_y, gyro_z).".format(imu_raw_data[3], imu_raw_data[4], imu_raw_data[5]))
    print("euler = {:>3.1f}, {:>3.1f}, {:>3.1f}. Sequence (roll, pitch, yaw).".format(imu_euler_data[0], imu_euler_data[1], imu_euler_data[2]))
    print("quar  = {:>f}, {:>f}, {:>f}, {:>f}.Sequence (x, y, z, w).".format(imu_quar_data[0], imu_quar_data[1], imu_quar_data[2], imu_quar_data[3]))

    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        pit1.stop()  # pyright: ignore[reportUndefinedVariable]
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()

# 如何换算 IMU 数据到物理数值
# 需要在模块的资料中找到对应芯片的手册
# 手册中通常会标注芯片的 Sensitivity 灵敏度

# 以加速度为例 其手册描述可能是 LSB/g 或者 mg/LSB
# LSB/g 代表多少数值变化对应一个 g 的加速度变化
# mg/LSB 代表每个 mg 加速度变化对应多少数值变化
# 假设手册描述的是 ±8g 量程下灵敏度为 4096 LSB/g 或者 0.244 mg/LSB
# 那么假设获取的加速度值为 4091 此时对应的换算方式为
# 4091 / 4096           = 0.998779g (灵敏度为 4096 LSB/g)
# 4091 * 0.244 / 1000   = 0.998204g (灵敏度为 0.244 mg/LSB)

# 同理 陀螺仪 磁力计 的数据也是在手册中找到对应灵敏度描述进行换算
