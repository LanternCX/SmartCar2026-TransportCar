from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from control.wheel import build_wheel_state
from control.pid_controller import IncrementalPIDController
from control.pid_math import compute_pi_from_id, reset_pi_state
from control.pid_store import save_pid_params
from control.ident_tools import (
    create_ident_buffers,
    push_ident_sample,
    get_ident_samples,
    identify_wheel,
)
import gc


TICK_MS = 5  # 采样/控制周期 (ms)
MAX_DUTY = 10000  # 占空比上限
IDENT_STEP_DUTY = 5000  # 辨识阶跃幅值
IDENT_DURATION_MS = 4000  # 辨识持续时间
IDENT_MAX_SAMPLES = min(IDENT_DURATION_MS // TICK_MS + 10, 600)  # 环形缓存深度
TARGET_WHEELS = ("m", "l", "r")  # 参与辨识的电机
HARDNESS = "soft"  # IMC 硬度（越小越激进）
KP_MAX = 200.0  # KP 安全上限（降低防止过激）
KI_MAX = 20000.0  # KI 安全上限（降低防止过激）
GAIN_BOOST = 0.5  # 额外增益倍数（降低整体环路增益）
PID_PARAM_FILE = "/flash/pid_params.txt"  # 保存位置


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
identifying = True
ident_start_tick = None


def pit_handler(tick):
    global pit_flag
    pit_flag = True


pit1 = ticker(1)
pit1.capture_list(*[state["encoder"] for state in wheel_states])
pit1.callback(pit_handler)
pit1.start(TICK_MS)

ident_samples = create_ident_buffers(TARGET_WHEELS, IDENT_MAX_SAMPLES)

while True:
    if pit_flag:
        tick_count += 1
        led.toggle()
        # 读取编码器并做滤波
        for state in wheel_states:
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            smooth_raw = state["input_lpf"].update(raw)
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)
        t_ms = tick_count * TICK_MS

        if identifying:
            if ident_start_tick is None:
                ident_start_tick = tick_count

            # 施加阶跃，采集响应
            for state in wheel_states:
                if state["name"] in TARGET_WHEELS:
                    state["motor"].duty(IDENT_STEP_DUTY)
                else:
                    state["motor"].duty(0)

            for state in wheel_states:
                if state["name"] in TARGET_WHEELS:
                    push_ident_sample(
                        state["name"],
                        t_ms,
                        state["filtered_speed"],
                        ident_samples,
                        IDENT_MAX_SAMPLES,
                    )

            if (t_ms - ident_start_tick * TICK_MS) >= IDENT_DURATION_MS:
                # 辨识结束，计算参数并保存
                for motor in all_motors:
                    motor.duty(0)
                for state in wheel_states:
                    if state["name"] in TARGET_WHEELS:
                        samples = get_ident_samples(
                            state["name"], ident_samples, IDENT_MAX_SAMPLES
                        )
                        g, tau = identify_wheel(samples, IDENT_STEP_DUTY)
                    else:
                        g, tau = None, None
                    state["id_gain"] = g
                    state["id_tau"] = tau
                    if g and tau:
                        kp, ki = compute_pi_from_id(
                            g, tau, HARDNESS, KP_MAX, KI_MAX, GAIN_BOOST
                        )
                        state["kp"], state["ki"] = kp, ki
                        state["controller"].set_gains(kp, ki)
                reset_pi_state(wheel_states)
                identifying = False
                save_pid_params(PID_PARAM_FILE, wheel_states, HARDNESS)
                uart3.write("id_done\r\n")
                pit1.stop()
                break

        pit_flag = False

    if switch2.value() != state2:
        pit1.stop()
        for motor in all_motors:
            motor.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
