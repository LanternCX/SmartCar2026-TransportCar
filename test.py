from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from control.wheel import build_wheel_state
from control.pid_controller import IncrementalPIDController
from control.pid_math import clamp, compute_pi_from_id
from control.pid_store import load_pid_params
import gc


TICK_MS = 5  # 采样/控制周期 (ms)
MAX_DUTY = 5000  # 占空比上限，匹配期望 2000-5000 区间
TARGET_SPEEDS = {"m": 5.0, "l": 5.0, "r": 5.0}  # 默认目标速度
TARGET_SPEED_MAX = 30.0  # 目标速度安全上限
ACTIVE_WHEELS = ("m", "l", "r")  # 参与闭环的电机
HARDNESS = "soft"  # 若文件无硬度则回退此值
KP_MAX = 200.0  # 与辨识脚本一致的安全上限
KI_MAX = 20000.0
GAIN_BOOST = 0.5  # 与辨识脚本保持一致
PID_PARAM_FILE = "/flash/pid_params.txt"  # PID 参数存储位置


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
        pid_controller=IncrementalPIDController(output_limit=MAX_DUTY),
    ),
    build_wheel_state(
        "l",
        encoder_l,
        motor_l,
        TICK_MS,
        30,
        8,
        pid_controller=IncrementalPIDController(output_limit=MAX_DUTY),
    ),
    build_wheel_state(
        "r",
        encoder_r,
        motor_r,
        TICK_MS,
        30,
        8,
        pid_controller=IncrementalPIDController(output_limit=MAX_DUTY),
    ),
]
all_motors = [state["motor"] for state in wheel_states]

pit_flag = False
tick_count = 0
target_speeds = dict(TARGET_SPEEDS)


def pit_handler(tick):
    global pit_flag
    pit_flag = True


def load_and_apply_pid():
    meta = load_pid_params(PID_PARAM_FILE)
    hardness_from_file = meta.get("hardness")
    hardness_used = hardness_from_file or HARDNESS
    if not meta.get("params"):
        uart3.write("pid_file_missing\r\n")
        return hardness_used

    for state in wheel_states:
        params = meta["params"].get(state["name"])
        if not params:
            continue
        state["id_gain"] = params.get("gain")
        state["id_tau"] = params.get("tau")
        # 优先使用文件中已有的 kp/ki；如缺失则根据辨识值重新计算
        kp_saved = params.get("kp")
        ki_saved = params.get("ki")
        kp_val = state.get("kp", 0.0)
        ki_val = state.get("ki", 0.0)
        if kp_saved is not None and ki_saved is not None:
            kp_val, ki_val = kp_saved, ki_saved
        elif state["id_gain"] and state["id_tau"]:
            kp_val, ki_val = compute_pi_from_id(
                state["id_gain"],
                state["id_tau"],
                hardness_used,
                KP_MAX,
                KI_MAX,
                GAIN_BOOST,
            )
        state["kp"], state["ki"] = kp_val, ki_val
        state["controller"].set_gains(kp_val, ki_val)
    return hardness_used


pit1 = ticker(1)
pit1.capture_list(*[state["encoder"] for state in wheel_states])
pit1.callback(pit_handler)
pit1.start(TICK_MS)

load_and_apply_pid()

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
