"""速度环测试与调试脚本

@file src/script/test.py
@brief 独立于主控制系统的速度环单轮闭环测试工具

@details 此脚本用于逐轮进行速度环闭环测试, 验证 PID 参数效果, 无需完整的视觉/决策系统
"""
from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from config import comm as comm_params
from config import motion as motion_params
from config import safety as safety_params
from config import storage as storage_params
from control.wheel import build_wheel_state
from control.pid_controller import SpeedPIDController
from control.pid_store import load_ident_params
from control.pid_math import clamp
from filters.spike_filter import SpikeMedianFilter
from filters.diff_limit_filter import DiffLimitFilter
import gc


# 采样/控制周期, 单位毫秒
TICK_MS = getattr(motion_params, "TICK_MS")
# PWM 占空比上限, 范围 0 ~ 10000
MAX_DUTY = getattr(safety_params, "MAX_DUTY")
# 默认目标速度, 单位 m/s, 可在运行时通过命令修改
TARGET_SPEEDS = {"m": 0.0, "l": -5.0, "r": 5.0}
# 目标速度安全上限, 超过此值的指令会被截断
TARGET_SPEED_MAX = getattr(safety_params, "TARGET_SPEED_MAX")
# 参与闭环的电机列表
ACTIVE_WHEELS = getattr(motion_params, "ACTIVE_WHEELS")
# ACTIVE_WHEELS = ("r",)

# 辨识参数文件路径, 用于加载电机增益和时间常数
IDENT_RESULTS_FILE = getattr(storage_params, "IDENT_RESULTS_FILE")

# PID_MAP = {
#     "m": (100, 500, 1)
#     "l": (100, 500, 1)
#     "r": (100, 500, 1)
# }

# 初始 PID 参数 (P, D, P2 前馈), 全为 0 用于调试
PID_MAP = {
    "m": (0, 0, 0),
    "l": (0, 0, 0),
    "r": (0, 0, 0),
}


def load_ident_lookup(path):
    """从文件加载辨识的 (gain, tau) 映射

    参数:
        path: 辨识参数文件路径

    返回:
        字典 {轮子名 -> (gain, tau)}
    """
    meta = load_ident_params(path)
    lookup = {}
    for name, vals in meta.items():
        lookup[name] = (vals.get("gain"), vals.get("tau"))
    return lookup

UART_BAUDRATE = getattr(comm_params, "UART_BAUDRATE")


uart3 = UART(2)
uart3.init(UART_BAUDRATE)

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


ident_lookup = load_ident_lookup(IDENT_RESULTS_FILE)

wheel_states = []
for name, enc, mot in (
    ("m", encoder_m, motor_m),
    ("l", encoder_l, motor_l),
    ("r", encoder_r, motor_r),
):
    gain_tau = ident_lookup.get(name, (None, None))
    controller = SpeedPIDController(
        output_limit=MAX_DUTY, plant_gain=gain_tau[0], plant_tau=gain_tau[1]
    )
    wheel_states.append(
        build_wheel_state(
            name,
            enc,
            mot,
            TICK_MS,
            30,
            8,
            pid_controller=controller,
        )
    )
# 替换输入端滤波为中值滤波以削弱尖刺
for state in wheel_states:
    state["input_lpf"] = SpikeMedianFilter(window=5)
    state["diff_filter"] = DiffLimitFilter(max_delta=5.0)
all_motors = [state["motor"] for state in wheel_states]

pit_flag = False
tick_count = 0
target_speeds = dict(TARGET_SPEEDS)


def pit_handler(tick):
    """PIT 中断处理程序,标记进行一次控制周期

    参数:
        tick: 中断参数(未使用)

    副作用:
        设置全局 pit_flag 为 True,主循环据此执行一次速度环计算
    """
    global pit_flag
    pit_flag = True



def init_pid():
    """初始化速度环 PID 参数

    从 PID_MAP 读取每个轮子的增益配置,同步辨识参数以供调试显示
    """
    for state in wheel_states:
        kp_val, ki_val, ki2_val = PID_MAP.get(state["name"], (10.0, 0.5, 0.01))
        state["kp"], state["ki"] = kp_val, ki_val
        state["controller"].set_gains(kp_val, ki_val, ki2_val)
        # 同步辨识出的模型参数到状态,便于调试查看
        state["id_gain"], state["id_tau"] = (
            state["controller"].plant_gain,
            state["controller"].plant_tau,
        )


pit1 = ticker(1)
pit1.capture_list(*[state["encoder"] for state in wheel_states])
pit1.callback(pit_handler)
pit1.start(TICK_MS)

init_pid()

# 主控制循环
while True:
    if pit_flag:
        tick_count += 1
        led.toggle()
        # 读取编码器并通过多级滤波器处理
        for state in wheel_states:
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            smooth_raw = state["input_lpf"].update(raw)
            smooth_raw = state["diff_filter"].update(smooth_raw)
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)

        dt_s = TICK_MS / 1000.0
        # 闭环控制:速度环 PI 输出占空比
        for state in wheel_states:
            if state["name"] in ACTIVE_WHEELS:
                tgt = clamp(
                    target_speeds.get(state["name"], 0.0),
                    -TARGET_SPEED_MAX,
                    TARGET_SPEED_MAX,
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

        # 输出采样数据用于波形分析
        sample = ",".join(
            "{:.2f}".format(v)
            for state in wheel_states
            for v in (state["raw_speed"], state["filtered_speed"], state["duty"])
        )
        uart3.write(sample + "\r\n")

        pit_flag = False

    # 硬件急停:检测到开关改变则停止
    if switch2.value() != state2:
        pit1.stop()
        for motor in all_motors:
            motor.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
