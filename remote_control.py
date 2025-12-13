from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER
from smartcar import encoder, ticker
from control.wheel import build_wheel_state
from control.pid_controller import IncrementalPIDController
from control.pid_math import clamp, compute_pi_from_id, reset_pi_state
from control.pid_store import load_pid_params
import gc
import math


TICK_MS = 5  # 采样/控制周期 (ms)
MAX_DUTY = 7000  # 占空比上限
V_CMD_MAX = 1000  # 命令输入限幅
TARGET_SPEED_MAX = 3000.0  # 轮速目标限幅（编码器单位）
ACTIVE_WHEELS = ("m", "l", "r")
HARDNESS = "soft"
KP_MAX = 200.0
KI_MAX = 20000.0
GAIN_BOOST = 0.5
PID_PARAM_FILE = "/flash/pid_params.txt"


led = Pin("C4", Pin.OUT, value=True)
switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
switch2_init = switch2.value()

uart3 = UART(2)
uart3.init(115200)

# wheel mapping: m=center, l=left, r=right
encoder_m = encoder("D15", "D16", True)
encoder_l = encoder("C0", "C1", True)
encoder_r = encoder("C2", "C3", True)

motor_m = MOTOR_CONTROLLER(
    MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False
)
motor_l = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D4_DIR_D5, 13000, duty=0, invert=False)
motor_r = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D6_DIR_D7, 13000, duty=0, invert=True)

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
target_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
last_cmd = {"vx": 0, "vy": 0, "omega": 0}
rx_buf = ""


def pit_handler(_tick):
    """
    设置定时中断标志

    :param _tick: 由 ticker 提供的计数（未使用）
    """
    global pit_flag
    pit_flag = True


def init_pid():
    """
    初始化 PID 控制器参数
    """
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


def inverse_kinematics(vx, vy, omega):
    """
    逆向运动学解算

    :param vx: 横向速度分量
    :param vy: 纵向速度分量
    :param omega: 角速度分量
    """
    sqrt3 = math.sqrt(3)
    # m: front, l: left, r: right (与原脚本 motor_1/3/4 对应)
    vl = (vx / 3.0) + (sqrt3 / 3.0) * vy + (omega / 3.0)
    vr = (vx / 3.0) - (sqrt3 / 3.0) * vy + (omega / 3.0)
    vm = (-2.0 / 3.0) * vx + (omega / 3.0)

    speeds = [abs(vm), abs(vl), abs(vr)]
    max_speed = max(speeds) if speeds else 0.0
    if max_speed > TARGET_SPEED_MAX and max_speed > 0.0:
        scale = TARGET_SPEED_MAX / max_speed
        vm *= scale
        vl *= scale
        vr *= scale

    return vm, vl, vr


def parse_command(cmd_str):
    """
    解析命令字符串

    :param cmd_str: 命令字符串，格式为 "vx,vy,omega" 或 "vx vy omega"
    """
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return None
    parts = cmd_str.split(",") if "," in cmd_str else cmd_str.split()
    if len(parts) < 3:
        uart3.write("ERR need 3 vals\r\n")
        return None

    try:
        vx = int(parts[0].strip())
        vy = int(parts[1].strip())
        omega = int(parts[2].strip())
    except Exception:
        uart3.write("ERR parse int\r\n")
        return None

    vx = clamp(vx, -V_CMD_MAX, V_CMD_MAX)
    vy = clamp(vy, -V_CMD_MAX, V_CMD_MAX)
    omega = clamp(omega, -V_CMD_MAX, V_CMD_MAX)
    return {"vx": vx, "vy": vy, "omega": omega}


def apply_command(cmd):
    """
    应用解析后的命令并设置目标速度

    :param cmd: 包含 vx, vy, omega 的命令字典
    """

    global target_speeds, last_cmd
    if not cmd:
        return
    last_cmd = cmd
    vm, vl, vr = inverse_kinematics(cmd["vx"], cmd["vy"], cmd["omega"])
    target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
    target_speeds["l"] = clamp(vl, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
    target_speeds["r"] = clamp(vr, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
    uart3.write(
        "OK vx=%d vy=%d om=%d -> m=%.1f l=%.1f r=%.1f\r\n"
        % (
            cmd["vx"],
            cmd["vy"],
            cmd["omega"],
            target_speeds["m"],
            target_speeds["l"],
            target_speeds["r"],
        )
    )


def print_help():
    """打印串口帮助信息"""

    uart3.write("\r\n=== Three-wheel omni control ===\r\n")
    uart3.write("cmd: vx,vy,omega (ints)\r\n")
    uart3.write("range: -%d ~ %d\r\n" % (V_CMD_MAX, V_CMD_MAX))
    uart3.write("example: 500,0,0 or 0 0 300\r\n\r\n")


pit1 = ticker(1)
pit1.capture_list(*[state["encoder"] for state in wheel_states])
pit1.callback(pit_handler)
pit1.start(TICK_MS)

init_pid()
print_help()
uart3.write("ready\r\n")

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

        dt_s = TICK_MS / 1000.0
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

        sample = ",".join(
            "{:.2f}".format(v)
            for state in wheel_states
            for v in (state["raw_speed"], state["filtered_speed"], state["duty"])
        )
        uart3.write(sample + "\r\n")

        pit_flag = False

    buf_len = uart3.any()
    if buf_len:
        try:
            rx_buf += uart3.read(buf_len).decode()
            while True:
                idx = rx_buf.find("\n")
                if idx == -1:
                    break
                line = rx_buf[:idx].rstrip("\r")
                rx_buf = rx_buf[idx + 1 :]
                if not line:
                    continue
                uart3.write("RCV: %s\r\n" % line)
                apply_command(parse_command(line))
        except Exception as exc:
            uart3.write("ERR %s\r\n" % exc)

    if switch2.value() != switch2_init:
        pit1.stop()
        reset_pi_state(wheel_states)
        for motor in all_motors:
            motor.duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
