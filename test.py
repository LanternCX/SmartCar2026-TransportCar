from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from filters.dual_window_regression_filter import DualWindowRegressionFilter
from filters.lowpass_filter import LowPassFilter
import gc

# 配置项
TICK_MS = 5
MAX_DUTY = 10000
DUTY_STEP = 10

# UART 调试
uart3 = UART(2)
uart3.init(115200)

# LED 与拨码开关
led = Pin('C4', Pin.OUT, value=True)
switch2 = Pin('D9', Pin.IN, pull=Pin.PULL_UP_47K)
state2 = switch2.value()

# 编码器与 PWM
encoder_1 = encoder("D15", "D16", True)
motor_1 = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False)

# 采样 ticker
pit_flag = False
def pit_handler(tick):
    global pit_flag
    pit_flag = True

pit1 = ticker(1)
pit1.capture_list(encoder_1)
pit1.callback(pit_handler)
pit1.start(TICK_MS)

# 滤波器
dual_filter = DualWindowRegressionFilter(
    tick_ms=TICK_MS,
    long_window=30,
    short_window=8,
    combine_w=0.65
)

# 输出低通滤波器（对回归融合后的速度做低通）
output_lpf = LowPassFilter(alpha=0.5)
input_lpf = LowPassFilter(alpha=0.5)

now_duty = 0

while True:
    if pit_flag:
        led.toggle()
        raw_speed = float(encoder_1.get())
        smooth_raw_speed = input_lpf.update(raw_speed)
        fused_speed, accel, _ = dual_filter.update(smooth_raw_speed)
        smooth_speed = output_lpf.update(fused_speed)
        uart3.write("{:.2f},{:.2f},{:.2f}\r\n".format(smooth_speed, raw_speed, accel))
        pit_flag = False

        motor_1.duty(now_duty)
        now_duty += DUTY_STEP
        if now_duty > MAX_DUTY:
            now_duty = MAX_DUTY

    if switch2.value() != state2:
        pit1.stop()
        motor_1.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
