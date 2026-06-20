"""PID 参数系统辨识脚本

@file src/script/pid_identify.py
@brief 通过阶跃激励来辨识电机的一阶系统参数, 并计算最优 PI 增益

@details 通过阶跃输入激励电机, 采集速度响应, 辨识一阶系统参数 (增益、时间常数), 最后计算最优 PI 增益并保存至 Flash

流程:
1. 启动 PIT 中断 (5ms 周期)
2. 依次对三轮施加 IDENT_STEP_DUTY 占空比, 持续 IDENT_DURATION_MS 毫秒
3. 记录速度响应
4. 对每轮进行一阶系统辨识
5. 使用辨识结果反演计算 PI 增益
6. 保存结果到 Flash
"""
from machine import Pin, UART
from smartcar import ticker
from config import comm as comm_params
from config import motion as motion_params
from config import safety as safety_params
from config import storage as storage_params
from control.wheel import build_wheel_state
from control.pid_controller import IncrementalPIDController
from control.pid_math import compute_pi_from_id, reset_pi_state
from control.pid_store import save_pid_params, save_ident_params
from control.ident_tools import (
    create_ident_buffers,
    push_ident_sample,
    get_ident_samples,
    identify_wheel,
)
from hardware.encoders import create_encoders
from hardware.motors import create_motors
from vision.vehicle_role import read_vehicle_role
import gc


# 采样/控制周期, 单位毫秒
TICK_MS = getattr(motion_params, "TICK_MS")
# PWM 占空比上限, 范围 0 ~ 10000
MAX_DUTY = getattr(safety_params, "MAX_DUTY")
# 辨识阶跃幅值, 单位为占空比值, 施加到电机的激励强度
IDENT_STEP_DUTY = 2000
# 辨识持续时间, 单位毫秒, 每轮的激励持续时长
IDENT_DURATION_MS = 4000
# 环形缓存深度, 用于存储速度采样历史
IDENT_MAX_SAMPLES = min(IDENT_DURATION_MS // TICK_MS + 10, 600)
# 参与辨识的电机列表 (中心、左、右)
TARGET_WHEELS = ("m", "l", "r")
# IMC 硬度参数 (越小越激进), 影响 PI 增益计算的保守程度
HARDNESS = "soft"
# KP 安全上限, 防止计算结果过激
KP_MAX = 200.0
# KI 安全上限, 防止计算结果过激
KI_MAX = 20000.0
# 额外增益倍数, 用于降低整体环路增益, 增加系统稳定性裕度
GAIN_BOOST = 0.5
# PID 参数保存路径, 用于后续控制环节加载
PID_PARAM_FILE = "/flash/pid_params.txt"
# 辨识结果记录路径, 用于记录时间常数和增益
IDENT_RESULTS_FILE = getattr(storage_params, "IDENT_RESULTS_FILE")

UART_BAUDRATE = getattr(comm_params, "UART_BAUDRATE")


uart3 = UART(2)
uart3.init(UART_BAUDRATE)

led = Pin("C4", Pin.OUT, value=True)
switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
state2 = switch2.value()

vehicle_role = read_vehicle_role()
encoders = create_encoders(vehicle_role)
motors = create_motors(vehicle_role)


wheel_states = [
    build_wheel_state(
        "m",
        encoders["m"],
        motors["m"],
        TICK_MS,
        30,
        8,
        pid_controller=IncrementalPIDController(output_limit=MAX_DUTY),
    ),
    build_wheel_state(
        "l",
        encoders["l"],
        motors["l"],
        TICK_MS,
        30,
        8,
        pid_controller=IncrementalPIDController(output_limit=MAX_DUTY),
    ),
    build_wheel_state(
        "r",
        encoders["r"],
        motors["r"],
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
    """PIT 中断处理程序,标记进行一次控制周期

    参数:
        tick: 中断参数(未使用)

    副作用:
        设置全局 pit_flag 为 True,主循环据此执行一次辨识采样周期
    """
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

            # 施加阶跃,采集响应
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
                        state["filtered_speed"] / 3,
                        ident_samples,
                        IDENT_MAX_SAMPLES,
                    )

            if (t_ms - ident_start_tick * TICK_MS) >= IDENT_DURATION_MS:
                # 辨识结束,计算参数并保存
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
                save_ident_params(IDENT_RESULTS_FILE, wheel_states)
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
