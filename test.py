from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from filters.dual_window_regression_filter import DualWindowRegressionFilter
from filters.lowpass_filter import LowPassFilter
import gc

# 配置项
TICK_MS = 5
MAX_DUTY = 5000
DUTY_STEP = 10

# UART 调试
uart3 = UART(2)
uart3.init(115200)

# LED 与拨码开关
led = Pin("C4", Pin.OUT, value=True)
switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
state2 = switch2.value()

# 编码器与 PWM
encoder_m = encoder("D15", "D16", True)
encoder_l = encoder("C0", "C1", True)
encoder_r = encoder("C2", "C3", True)

motor_m = MOTOR_CONTROLLER(
    MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False
)
motor_l = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D6_DIR_D7, 13000, duty=0, invert=True)
motor_r = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D4_DIR_D5, 13000, duty=0, invert=False)


def build_wheel_state(name, encoder_obj, motor_obj):
    return {
        "name": name,
        "encoder": encoder_obj,
        "motor": motor_obj,
        "dual_filter": DualWindowRegressionFilter(
            tick_ms=TICK_MS,
            long_window=30,
            short_window=8,
            combine_w=0.65,
        ),
        "input_lpf": LowPassFilter(alpha=0.5),
        "output_lpf": LowPassFilter(alpha=0.5),
        "raw_speed": 0.0,
        "filtered_speed": 0.0,
    }


wheel_states = [
    build_wheel_state("m", encoder_m, motor_m),
    build_wheel_state("l", encoder_l, motor_l),
    build_wheel_state("r", encoder_r, motor_r),
]
all_motors = [state["motor"] for state in wheel_states]

# 采样 ticker
pit_flag = False


def pit_handler(tick):
    global pit_flag
    pit_flag = True


pit1 = ticker(1)
pit1.capture_list(*[state["encoder"] for state in wheel_states])
pit1.callback(pit_handler)
pit1.start(TICK_MS)

# 滤波器负责在 wheel_states 中单独构造
now_duty = 0

while True:
    if pit_flag:
        led.toggle()
        for state in wheel_states:
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            smooth_raw = state["input_lpf"].update(raw)
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)
        sample = ",".join(
            "{:.2f}".format(v)
            for state in wheel_states
            for v in (state["raw_speed"], state["filtered_speed"])
        )
        uart3.write(sample + "\r\n")
        pit_flag = False

        # for i in range(len(all_motors)):
        #     if i == 1:
        #         continue
        #     all_motors[i].duty(now_duty)
        for motor in all_motors:
            motor.duty(now_duty)
        now_duty = min(now_duty + DUTY_STEP, MAX_DUTY)

    if switch2.value() != state2:
        pit1.stop()
        for motor in all_motors:
            motor.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
