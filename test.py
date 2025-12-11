from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from filters.dual_window_regression_filter import DualWindowRegressionFilter
from filters.lowpass_filter import LowPassFilter
from array import array
import math
import gc

# 配置项
TICK_MS = 5  # 控制与采样周期（ms）
MAX_DUTY = 10000  # 最大允许占空比
IDENT_STEP_DUTY = 5000  # 系统辨识时的阶跃占空比，注意安全范围

# 缩短辨识时间并限制缓存深度，避免 MicroPython 内存不足
IDENT_DURATION_MS = 4000
IDENT_MAX_SAMPLES = min(IDENT_DURATION_MS // TICK_MS + 10, 600)

# 为每个轮子单独设置默认目标转速（单位依编码器刻度而定）
TARGET_SPEEDS = {"m": 5.0, "l": 5.0, "r": 5.0}
TARGET_SPEED_MAX = 30.0  # 速度设定上限
ACTIVE_WHEELS = ("m", "l", "r")  # 三电机均闭环

# 硬度（控制激进程度）可选: "soft" | "mid" | "hard"
HARDNESS = "hard3"

# 控制器参数安全限幅，防止异常辨识导致过大增益
KP_MAX = 25.0
KI_MAX = 400.0
GAIN_BOOST = 3.0  # 额外增益倍数，用于更硬的速度环

# UART 调试
uart3 = UART(2)
uart3.init(115200)

# LED 与拨码开关
led = Pin("C4", Pin.OUT, value=True)
switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
state2 = switch2.value()

# 编码器与 PWM
encoder_m = encoder("D15", "D16", True)
encoder_l = encoder("C2", "C3", True)
encoder_r = encoder("C0", "C1", True)

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
        "output_lpf": LowPassFilter(alpha=0.9),
        "raw_speed": 0.0,
        "filtered_speed": 0.0,
        "duty": 0.0,
        "kp": 0.0,
        "ki": 0.0,
        "prev_err": 0.0,
        "id_gain": None,
        "id_tau": None,
    }


wheel_states = [
    build_wheel_state("m", encoder_m, motor_m),
    build_wheel_state("l", encoder_l, motor_l),
    build_wheel_state("r", encoder_r, motor_r),
]
all_motors = [state["motor"] for state in wheel_states]

# 采样 ticker
pit_flag = False
tick_count = 0
identifying = True
ident_start_tick = None
target_speeds = dict(TARGET_SPEEDS)


def hardness_factor(name):
    if name == "soft":
        return 4.0
    if name == "hard":
        return 1.0
    if name == "hard2":
        return 0.5
    if name == "hard3":
        return 0.05
    return 2.0  # mid


def clamp(val, lo, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def compute_pi_from_id(gain, tau, hardness_name):
    # IMC 型整定：C(s) = (tau s + 1) / (K * lambda s)
    lam = tau * hardness_factor(hardness_name)
    kp = (tau / (gain * lam)) * GAIN_BOOST
    ki = (1.0 / (gain * lam)) * GAIN_BOOST
    return clamp(kp, 0.0, KP_MAX), clamp(ki, 0.0, KI_MAX)


def push_ident_sample(name, t_ms, val, buf):
    slot = buf[name]
    idx = slot["count"] % IDENT_MAX_SAMPLES
    slot["t"][idx] = t_ms
    slot["v"][idx] = val
    slot["count"] += 1


def get_ident_samples(name, buf):
    slot = buf[name]
    n = min(slot["count"], IDENT_MAX_SAMPLES)
    if n == 0:
        return []
    start = (slot["count"] - n) % IDENT_MAX_SAMPLES
    samples = []
    for i in range(n):
        idx = (start + i) % IDENT_MAX_SAMPLES
        samples.append((slot["t"][idx], slot["v"][idx]))
    return samples


def identify_wheel(state, samples):
    if not samples:
        return None, None
    # 使用末尾样本估计稳态
    tail = samples[-min(len(samples), 40) :]
    steady = sum(val for _, val in tail) / len(tail)
    gain = steady / IDENT_STEP_DUTY if IDENT_STEP_DUTY != 0 else 0.0
    if gain <= 0:
        return None, None

    target63 = steady * 0.632
    t0 = samples[0][0]
    tau = None

    # 1) 首选 63% 上升时间
    for t_ms, val in samples:
        if val >= target63:
            tau = max((t_ms - t0) / 1000.0, 0.01)
            break

    # 2) 若未到 63%，用对数线性回归估计 tau
    if tau is None:
        xs = []
        zs = []
        for t_ms, val in samples:
            if val < steady and steady > 1e-6:
                x = (t_ms - t0) / 1000.0
                r = 1.0 - val / steady
                if r > 0.0:
                    xs.append(x)
                    zs.append(math.log(r))
        if xs:
            num = sum(x * z for x, z in zip(xs, zs))
            den = sum(x * x for x in xs)
            if den > 0 and num < 0:
                tau_est = -den / num  # 因为 z = -t/tau -> slope = num/den
                tau = max(tau_est, 0.01)

    if tau is None:
        return None, None
    return gain, tau


def recompute_gains(hardness_name):
    for state in wheel_states:
        if state["id_gain"] and state["id_tau"]:
            state["kp"], state["ki"] = compute_pi_from_id(
                state["id_gain"], state["id_tau"], hardness_name
            )


def reset_pi_state():
    for state in wheel_states:
        state["duty"] = 0.0
        state["prev_err"] = 0.0


def incremental_pi(state, target, dt_s):
    err = target - state["filtered_speed"]
    du = state["kp"] * (err - state["prev_err"]) + state["ki"] * err * dt_s
    duty = clamp(state["duty"] + du, -MAX_DUTY, MAX_DUTY)
    state["prev_err"] = err
    state["duty"] = duty
    return duty


def pit_handler(tick):
    global pit_flag
    pit_flag = True


pit1 = ticker(1)
pit1.capture_list(*[state["encoder"] for state in wheel_states])
pit1.callback(pit_handler)
pit1.start(TICK_MS)

# 滤波器负责在 wheel_states 中单独构造
now_duty = 0
ident_samples = {
    state["name"]: {
        "t": array("f", [0.0] * IDENT_MAX_SAMPLES),
        "v": array("f", [0.0] * IDENT_MAX_SAMPLES),
        "count": 0,
    }
    for state in wheel_states
}
recompute_gains(HARDNESS)

while True:
    if pit_flag:
        tick_count += 1
        led.toggle()
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
            # 施加阶跃占空比
            for state in wheel_states:
                if state["name"] in ACTIVE_WHEELS:
                    state["motor"].duty(IDENT_STEP_DUTY)
                else:
                    state["motor"].duty(0)
            for state in wheel_states:
                if state["name"] in ACTIVE_WHEELS:
                    push_ident_sample(
                        state["name"], t_ms, state["filtered_speed"], ident_samples
                    )
            if (t_ms - ident_start_tick * TICK_MS) >= IDENT_DURATION_MS:
                # 辨识结束
                for motor in all_motors:
                    motor.duty(0)
                for state in wheel_states:
                    if state["name"] in ACTIVE_WHEELS:
                        samples = get_ident_samples(state["name"], ident_samples)
                        g, tau = identify_wheel(state, samples)
                    else:
                        g, tau = None, None
                    state["id_gain"] = g
                    state["id_tau"] = tau
                    if g and tau:
                        state["kp"], state["ki"] = compute_pi_from_id(g, tau, HARDNESS)
                reset_pi_state()
                identifying = False
                uart3.write("id_done\r\n")
        else:
            dt_s = TICK_MS / 1000.0
            for state in wheel_states:
                if state["name"] in ACTIVE_WHEELS:
                    tgt = clamp(
                        target_speeds.get(state["name"], 0.0), 0.0, TARGET_SPEED_MAX
                    )
                    duty_cmd = incremental_pi(state, tgt, dt_s)
                    state["motor"].duty(int(duty_cmd))
                else:
                    state["duty"] = 0.0
                    state["prev_err"] = 0.0
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
