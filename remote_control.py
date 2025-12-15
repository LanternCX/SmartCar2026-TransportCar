from machine import Pin, UART
from seekfree import MOTOR_CONTROLLER, IMU660RX
from smartcar import encoder, ticker
from control.wheel import build_wheel_state
from control.pid_controller import SpeedPIDController
from control.pid_math import clamp, reset_pi_state
from control.pid_store import load_ident_params
from filters.lowpass_filter import LowPassFilter
from filters.spike_filter import SpikeMedianFilter
from filters.diff_limit_filter import DiffLimitFilter
import gc
import math

# 控制周期
TICK_MS = 5
# 占空比上限
MAX_DUTY = 10000
# 命令输入限幅
V_CMD_MAX = 1e3
# 轮速目标限幅
TARGET_SPEED_MAX = 30.0
# 启用的轮子，调试用
ACTIVE_WHEELS = ("m", "l", "r")

# 偏航角低通参数
GYRO_LPF_ALPHA = 0.2
# 角速度轴索引
GYRO_AXIS_Z = 5
# 偏航角 PD 控制参数
YAW_KP = 0.01
YAW_KD = 0.0005
# 自动回正最大角速度
AUTO_OMEGA_MAX = 15.0
# 保持静止模式速度阈值
HOLD_SPEED_EPS = 0.01

# 系统辨识参数文件路径
IDENT_RESULTS_FILE = "/flash/ident_params.txt"

# 三轮 PID 表
PID_MAP = {
    "m": (100, 500, 1),
    "l": (100, 500, 1),
    "r": (100, 500, 1),
}


def load_ident_lookup(path):
    """
    从文件加载辨识的 (gain, tau) 映射
    :param path: 文件路径
    :return: 名称到 (gain, tau) 的映射字典
    """
    meta = load_ident_params(path)
    lookup = {}
    for name, vals in meta.items():
        lookup[name] = (vals.get("gain"), vals.get("tau"))
    return lookup


# 核心板 LED
led = Pin("C4", Pin.OUT, value=True)
# 停止开关
switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
# 停止开关初始状态
switch2_init = switch2.value()

# 远程控制串口初始化
uart3 = UART(2)
uart3.init(115200)

# 后轮编码器
encoder_m = encoder("D15", "D16", True)
# 左轮编码器
encoder_l = encoder("C0", "C1", True)
# 右轮编码器
encoder_r = encoder("C2", "C3", True)

# IMU 660RAX 初始化
imu = IMU660RX()
# IMU 数据
imu_data = imu.get()
# 偏航角低通
gyro_lpf = LowPassFilter(alpha=GYRO_LPF_ALPHA, initial=0.0)
# 估计的航向角
heading_est = 0.0
# 目标航向角
heading_target = 0.0

# 后轮
motor_m = MOTOR_CONTROLLER(
    MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False
)
# 左轮
motor_l = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D4_DIR_D5, 13000, duty=0, invert=False)
# 右轮
motor_r = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D6_DIR_D7, 13000, duty=0, invert=True)

# 辨识参数
ident_lookup = load_ident_lookup(IDENT_RESULTS_FILE)

# 三轮状态列表
wheel_states = []
# 构造三轮状态列表
for name, enc, mot in (
    ("m", encoder_m, motor_m),
    ("l", encoder_l, motor_l),
    ("r", encoder_r, motor_r),
):
    gain_tau = ident_lookup.get(name, (None, None))
    controller = SpeedPIDController(
        output_limit=MAX_DUTY, plant_gain=gain_tau[0], plant_tau=gain_tau[1]
    )

    state = build_wheel_state(
        name,
        enc,
        mot,
        TICK_MS,
        30,
        8,
        pid_controller=controller,
    )
    state["input_lpf"] = SpikeMedianFilter(window=5)
    state["diff_filter"] = DiffLimitFilter(max_delta=5.0)
    wheel_states.append(state)

# 定时中断标志
pit_flag = False
# 定时中断计数
tick_count = 0
# 目标速度
target_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
# 上次命令
last_cmd = {"vx": 0, "vy": 0, "omega": 0}
# 串口接收缓冲
rx_buf = ""


def pit_handler(_tick):
    """
    设置定时中断标志

    :param _tick: 由 ticker 提供的计数（未使用）
    """
    global pit_flag
    pit_flag = True


def init_pid():
    """初始化 PID 控制器参数"""
    for state in wheel_states:
        kp_val, ki_val, ki2_val = PID_MAP.get(state["name"], (10.0, 0.5, 0.01))
        state["kp"], state["ki"] = kp_val, ki_val
        state["controller"].set_gains(kp_val, ki_val, ki2_val)


def inverse_kinematics(vx, vy, omega):
    """
    Y 车模逆运动学解算

    :param vx: 横向速度分量
    :param vy: 纵向速度分量
    :param omega: 角速度分量
    """
    sqrt3 = math.sqrt(3)
    # m: front, l: left, r: right
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


# 实例化 ticker 模块（周期中断）
pit1 = ticker(1)
# 配置捕获编码器和 IMU 数据
capture_items = [state["encoder"] for state in wheel_states]
capture_items.append(imu)
# 将各模块挂载到 ticker 的 capture_list 中
pit1.capture_list(*capture_items)
# 绑定 ticker 回调函数
pit1.callback(pit_handler)
# 以 TICK_MS 周期启动 ticker 模块
pit1.start(TICK_MS)

# 初始化 PID 控制器参数
init_pid()

while True:
    # 处理定时中断
    if pit_flag:
        # 定时器中断计数
        tick_count += 1
        # 切换 LED 状态
        led.toggle()

        # 时间增量（秒）
        dt_s = TICK_MS / 1000.0

        # 三轮编码器读取并滤波
        for state in wheel_states:
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            # 中值滤波
            smooth_raw = state["input_lpf"].update(raw)
            # 差分限幅
            smooth_raw = state["diff_filter"].update(smooth_raw)
            # 双窗线性回归滤波
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            # 低通滤波
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)

        # 角速度滤波与姿态回正控制
        yaw_raw = float(imu_data[GYRO_AXIS_Z]) if imu_data else 0.0
        yaw_rate = gyro_lpf.update(yaw_raw)
        heading_est += yaw_rate * dt_s

        # 处理角速度
        omega_cmd = last_cmd.get("omega", 0.0)
        # 只有在角速度较低时才启用自动回正
        hold_mode = abs(last_cmd.get("omega", 0)) < HOLD_SPEED_EPS
        if hold_mode:
            yaw_err = heading_target - heading_est
            omega_auto = clamp(
                YAW_KP * yaw_err - YAW_KD * yaw_rate,
                -AUTO_OMEGA_MAX,
                AUTO_OMEGA_MAX,
            )
            omega_cmd = omega_auto
        else:
            heading_target = heading_est

        # 根据当前指令与自动回正叠加后的角速度解算目标轮速
        vm, vl, vr = inverse_kinematics(
            float(last_cmd.get("vx", 0.0)),
            float(last_cmd.get("vy", 0.0)),
            float(omega_cmd),
        )
        target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
        target_speeds["l"] = clamp(vl, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
        target_speeds["r"] = clamp(vr, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)

        # 三轮速度环闭环控制
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

        # 打印串口调试信息
        sample = ",".join(
            "{:.2f}".format(v)
            for state in wheel_states
            for v in (state["raw_speed"], state["filtered_speed"], state["duty"])
        )
        uart3.write(sample + "\r\n")

        pit_flag = False

    # 处理串口命令
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

    # 处理停止开关
    if switch2.value() != switch2_init:
        pit1.stop()
        reset_pi_state(wheel_states)
        for state in wheel_states:
            state["motor"].duty(0)
        uart3.write("stop\r\n")
        break

    gc.collect()
