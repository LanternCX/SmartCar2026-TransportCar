from machine import *
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
import gc

# 调试用 UART3
uart3 = UART(2)
uart3.init(115200)

# LED 与 拨码开关
led = Pin('C4', Pin.OUT, value=True)
switch2 = Pin('D9', Pin.IN, pull=Pin.PULL_UP_47K)
state2 = switch2.value()

# 电机1 对应的编码器
encoder_1 = encoder("D15", "D16", True)

# 电机1 PWM 控制器
motor_1 = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False)

# 使用 PIT ticker 周期性触发编码器采样
ticker_flag = False

def time_pit_handler(tick):
    # ticker 回调，将标志位置位以在主循环处理中断
    global ticker_flag
    ticker_flag = True

pit1 = ticker(1)
pit1.capture_list(encoder_1)
pit1.callback(time_pit_handler)
pit1.start(10)

now_duty = 0
# 上一次原始编码器计数
pre_count = 0
now_speed = 0.0
MAX_DUTY = 5000

# 环形缓冲区，用于保存最近 N 帧的速度样本
BUF_LEN = 20
buf = [0.0] * BUF_LEN
buf_idx = 0
buf_count = 0
running_sum = 0.0
# 对 now_speed 的一阶低通滤波系数（0..1，越小越平滑）
SPEED_LPF_ALPHA = 0.3
# 低通滤波器的状态
smoothed_speed = 0.0

while True:
    if ticker_flag:
        led.toggle()
        raw = encoder_1.get()

        # 在相邻原始计数间做微平滑（使用浮点运算）
        if buf_count == 0:
            speed = float(raw)
        else:
            if pre_count != raw:
                speed = (raw + pre_count) / 2.0
            else:
                speed = float(raw)

        # 更新上一次原始计数
        pre_count = raw

        # 更新环形缓冲区和运行和
        if buf_count < BUF_LEN:
            running_sum += speed
            buf[buf_idx] = speed
            buf_idx = (buf_idx + 1) % BUF_LEN
            buf_count += 1
        else:
            # 覆盖最旧的值并调整运行和
            running_sum += speed - buf[buf_idx]
            buf[buf_idx] = speed
            buf_idx = (buf_idx + 1) % BUF_LEN

        now_speed = running_sum / buf_count if buf_count > 0 else 0.0

        # 对平均速度再做一阶低通滤波，得到更平滑的输出
        smoothed_speed = SPEED_LPF_ALPHA * now_speed + (1.0 - SPEED_LPF_ALPHA) * smoothed_speed

        # 通过 UART3 输出滤波后的速度（保留两位小数）
        uart3.write("{:.2f}\r\n".format(smoothed_speed))
        ticker_flag = False

        # 设置电机占空比并逐步增加（步进 10）
        motor_1.duty(now_duty)
        now_duty += 10
        now_duty = now_duty if now_duty <= MAX_DUTY else MAX_DUTY
        
    if switch2.value() != state2:
        # 停止测试：停止 ticker、关闭电机并输出停止信息
        pit1.stop()
        motor_1.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
