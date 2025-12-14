from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from control.wheel import build_wheel_state
from control.pid_controller import SpeedPIDController
from control.pid_math import clamp
import gc


# 采样/控制周期 (ms)
TICK_MS = 5
# 占空比上限，匹配期望 2000-5000 区间
MAX_DUTY = 5000
# 默认目标速度
TARGET_SPEEDS = {"m": 5.0, "l": 5.0, "r": 5.0}
# 目标速度安全上限
TARGET_SPEED_MAX = 30.0
# 参与闭环的电机
# ACTIVE_WHEELS = ("m", "l", "r")
ACTIVE_WHEELS = ("l",)

SPEED_PID_MAP = {
    "m": (600, 100, 0.00),
    "l": (3000, 300, 0.02),
    "r": (12.0, 0.6, 0.02),
}


uart3 = UART(2)
uart3.init(115200)

led = Pin("C4", Pin.OUT, value=True)
switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
state2 = switch2.value()

encoder_m = encoder("D15", "D16", True)
encoder_l = encoder("C2", "C3", True)
encoder_r = encoder("C0", "C1", True)

motor_m = MOTOR_CONTROLLER(
    MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False
)
motor_l = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D6_DIR_D7, 13000, duty=0, invert=True)
motor_r = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D4_DIR_D5, 13000, duty=0, invert=False)


wheel_states = [
    build_wheel_state(
        "m",
        encoder_m,
        motor_m,
        TICK_MS,
        30,
        8,
        pid_controller=SpeedPIDController(output_limit=MAX_DUTY),
    ),
    build_wheel_state(
        "l",
        encoder_l,
        motor_l,
        TICK_MS,
        30,
        8,
        pid_controller=SpeedPIDController(output_limit=MAX_DUTY),
    ),
    build_wheel_state(
        "r",
        encoder_r,
        motor_r,
        TICK_MS,
        30,
        8,
        pid_controller=SpeedPIDController(output_limit=MAX_DUTY),
    ),
]
all_motors = [state["motor"] for state in wheel_states]

pit_flag = False
tick_count = 0
target_speeds = dict(TARGET_SPEEDS)


def pit_handler(tick):
    global pit_flag
    pit_flag = True


def init_pid():
    """初始化速度环 PID 参数"""
    for state in wheel_states:
        kp_val, ki_val, ki2_val = SPEED_PID_MAP.get(state["name"], (10.0, 0.5, 0.01))
        state["kp"], state["ki"] = kp_val, ki_val
        state["controller"].set_gains(kp_val, ki_val, ki2_val)


pit1 = ticker(1)
pit1.capture_list(*[state["encoder"] for state in wheel_states])
pit1.callback(pit_handler)
pit1.start(TICK_MS)

init_pid()

while True:
    if pit_flag:
        tick_count += 1
        led.toggle()
        # 读取编码器并滤波
        for state in wheel_states:
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            smooth_raw = state["input_lpf"].update(raw)
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)

        dt_s = TICK_MS / 1000.0
        # 闭环控制：PI -> 占空比
        for state in wheel_states:
            if state["name"] in ACTIVE_WHEELS:
                tgt = clamp(
                    target_speeds.get(state["name"], 0.0), 0.0, TARGET_SPEED_MAX
                )
                duty_cmd = state["controller"].update(
                    tgt, state["filtered_speed"], dt_s
                )
                state["duty"] = duty_cmd
                state["motor"].duty(int(duty_cmd))
            else:
                state["controller"].reset()
                state["duty"] = 0.0
                state["motor"].duty(0)

        sample = ",".join(
            "{:.2f}".format(v)
            for state in wheel_states
            for v in (state["raw_speed"], state["filtered_speed"], state["duty"])
        )
        uart3.write(sample + "\r\n")

        pit_flag = False

    if switch2.value() != state2:
        pit1.stop()
        for motor in all_motors:
            motor.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
