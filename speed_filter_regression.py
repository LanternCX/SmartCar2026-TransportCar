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
TICK_MS = 10
pit_flag = False
lp_state = {'out': None, 'in': None}  # 低通滤波器内部状态

def time_pit_handler(tick):
    # ticker 回调，将标志位置位以在主循环处理中断
    global pit_flag
    pit_flag = True

pit1 = ticker(1)
pit1.capture_list(encoder_1)
pit1.callback(time_pit_handler)
pit1.start(TICK_MS)

# 一阶低通滤波器：旧值 0.3，新值 0.7，可按 key 复用不同通道状态
def lowpass(new_val, alpha=0.5, key='out'):
    state = lp_state.get(key)
    if state is None:
        state = new_val
    else:
        state = (1 - alpha) * state + alpha * new_val
    lp_state[key] = state
    return state

# 占空比逐步提升配置
now_duty = 0
MAX_DUTY = 5000
DUTY_STEP = 10

# 线性回归滑窗，拟合计数-时间斜率以平滑量化抖动
WINDOW = 30  # 样本数，对应 WINDOW * TICK_MS 毫秒窗口
vals = [0.0] * WINDOW   # 保存计数值
stamps = [0.0] * WINDOW # 保存时间戳（毫秒）
idx = 0
count = 0
sum_t = 0.0
sum_t2 = 0.0
sum_y = 0.0
sum_ty = 0.0
sample_idx = 0

while True:
    if pit_flag:
        led.toggle()
        raw = float(encoder_1.get())
        filt_raw = lowpass(raw, key='in')
        t_ms = sample_idx * TICK_MS
        sample_idx += 1

        if count < WINDOW:
            # 窗口未满，直接累加
            vals[count] = filt_raw
            stamps[count] = t_ms
            sum_t += t_ms
            sum_t2 += t_ms * t_ms
            sum_y += filt_raw
            sum_ty += filt_raw * t_ms
            count += 1
            continue
        else:
            # 窗口已满，滑动移除最旧样本
            old = vals[idx]
            old_t = stamps[idx]
            sum_t -= old_t
            sum_t2 -= old_t * old_t
            sum_y -= old
            sum_ty -= old * old_t

            vals[idx] = filt_raw
            stamps[idx] = t_ms
            sum_t += t_ms
            sum_t2 += t_ms * t_ms
            sum_y += filt_raw
            sum_ty += filt_raw * t_ms

            idx = (idx + 1) % WINDOW

        # 计算线性回归斜率 k 与截距 b（y = k*t + b）
        n = count
        denom = n * sum_t2 - sum_t * sum_t
        if denom != 0:
            slope = (n * sum_ty - sum_t * sum_y) / denom
            intercept = (sum_y - slope * sum_t) / n
        else:
            slope = 0.0
            intercept = 0.0

        # 预测下一采样点的速度（y 本身就是瞬时速度，线性回归用于平滑）
        next_t = (sample_idx + 1) * TICK_MS
        smooth_speed = slope * next_t + intercept

        # 斜率表示速度随时间的变化率，此处换算成“每秒速度增量”≈加速度
        accel = slope * 1000.0

        # 输出：平滑速度（预测下一点）、原始速度、速度变化率，逗号分隔
        uart3.write("{:.2f},{:.2f},{:.2f}\r\n".format(smooth_speed, float(raw), accel))
        pit_flag = False

        # 设置电机占空比并逐步增加
        motor_1.duty(now_duty)
        now_duty += DUTY_STEP
        if now_duty > MAX_DUTY:
            now_duty = MAX_DUTY

    if switch2.value() != state2:
        # 停止测试：停止 ticker、关闭电机并输出停止信息
        pit1.stop()
        motor_1.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
