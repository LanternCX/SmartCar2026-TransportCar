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
from utils.quaternion import Quaternion
from control.kinematics import OmniKinematics, Odometry
import gc
import math
import time

# 控制周期
TICK_MS = 5
# 占空比上限
MAX_DUTY = 10000
# 命令输入限幅
V_CMD_MAX = 1e3
# 轮速目标限幅 (Pulses per tick)
TARGET_SPEED_MAX = 30.0
# 位置控制最大速度 (m/s)
POS_MAX_SPEED = 0.05
# 位置控制比例系数 (Speed (m/s) / Error (m))
POS_KP = 2.0
# 位置锁定容差
POS_TOLERANCE = 0.05  # m
ANGLE_TOLERANCE = 5.0  # deg

# 启用的轮子，调试用
ACTIVE_WHEELS = ("m", "l", "r")

# 偏航角低通参数
GYRO_LPF_ALPHA = 0.2
# 陀螺仪比例因子 (LSB / (deg/s))
GYRO_SCALE = 16.384
# 角速度轴索引
GYRO_AXIS_Z = 5
# 偏航角 PD 控制参数
# 原参数对应 raw 数据，现在转为 deg，放大约 16.4 倍以保持控制力度
YAW_KP = 0.16
YAW_KD = 0.008
# 自动回正最大角速度 (对应轮子速度分量)
AUTO_OMEGA_MAX = 15.0
# 保持静止模式速度阈值
HOLD_SPEED_EPS = 0.01

# 系统辨识参数文件路径
IDENT_RESULTS_FILE = "/flash/ident_params.txt"
# 陀螺仪零飘参数文件路径
GYRO_OFFSET_FILE = "/flash/gyro_offset.txt"

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
uart3.write("System Starting...\r\n")

# 数据打印串口 (用于循环内高频输出)
uart6 = UART(5)
uart6.init(115200)

# 后轮编码器
encoder_m = encoder("D15", "D16", True)
# 左轮编码器
encoder_l = encoder("C0", "C1", True)
# 右轮编码器
encoder_r = encoder("C2", "C3", True)

# IMU 660RAX 初始化
uart3.write("Initializing IMU...\r\n")
imu = IMU660RX()
# IMU 数据
imu_data = imu.get()
# 偏航角低通
gyro_lpf = LowPassFilter(alpha=GYRO_LPF_ALPHA, initial=0.0)
# 估计的航向角
heading_est = 0.0
# 四元数估计姿态
q_est = Quaternion()
# 上次解算的 Yaw (弧度)，用于解包
last_yaw_rad = 0.0

# 运动学与里程计
kinematics = OmniKinematics()
odometry = Odometry()

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
uart3.write("Loading identify parameters...\r\n")
ident_lookup = load_ident_lookup(IDENT_RESULTS_FILE)

# 加载 IMU 零飘 (6轴)
imu_offsets = [0.0] * 6
try:
    with open(GYRO_OFFSET_FILE, "r") as f:
        content = f.read().strip()
        parts = content.split(",")
        if len(parts) == 6:
            imu_offsets = [float(x) for x in parts]
            uart3.write("Loaded IMU Offsets: {}\r\n".format(imu_offsets))
        else:
            # 兼容旧的单值格式 (仅 Gyro Z)
            imu_offsets[5] = float(content)
            uart3.write("Loaded Legacy Gyro Offset: {:.4f}\r\n".format(imu_offsets[5]))
except (OSError, ValueError):
    uart3.write("Gyro Offset file not found or invalid, using 0.0\r\n")

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
# 命令锁定标志
command_lock = False
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

    支持键值对格式: "dx=11, dy=-18, angle=-9.8"
    """
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return None

    # 简单重置命令
    if cmd_str == "reset":
        return {"reset": True}

    # 解析键值对
    parts = cmd_str.split(",")
    cmd = {}
    for part in parts:
        if "=" not in part:
            continue
        key, val_str = part.split("=", 1)
        key = key.strip().lower()
        try:
            val = float(val_str.strip())
        except ValueError:
            continue

        if key == "vx":
            cmd["vx"] = clamp(val, -V_CMD_MAX, V_CMD_MAX)
        elif key == "vy":
            cmd["vy"] = clamp(val, -V_CMD_MAX, V_CMD_MAX)
        elif key == "dx":
            cmd["dx"] = val
        elif key == "dy":
            cmd["dy"] = val
        elif key in ("omega", "w"):
            cmd["omega"] = clamp(val, -V_CMD_MAX, V_CMD_MAX)
        elif key in ("angle", "yaw"):
            cmd["angle"] = val
        elif key in ("d_angle", "dyaw", "da"):
            cmd["d_angle"] = val
        elif key == "x":
            cmd["x"] = val
        elif key == "y":
            cmd["y"] = val
        elif key == "reset":
            cmd["reset"] = val != 0

    return cmd if cmd else None


def apply_command(cmd):
    """
    应用解析后的命令并设置目标速度

    :param cmd: 包含 vx, vy, omega, angle 等的命令字典
    """
    global target_speeds, last_cmd, heading_target, heading_est, last_yaw_rad, command_lock
    if not cmd:
        return

    if cmd.get("reset"):
        # 1. 重置里程计
        odometry.reset()
        # 2. 重置航向角估计
        heading_est = 0.0
        heading_target = 0.0
        # 3. 重置四元数姿态
        q_est.w, q_est.x, q_est.y, q_est.z = 1.0, 0.0, 0.0, 0.0
        # 4. 重置解包相关的状态
        last_yaw_rad = 0.0
        # 5. 重置陀螺仪滤波状态
        gyro_lpf.reset(0.0)
        # 6. 重置 PID 控制器内部状态 (积分项)
        reset_pi_state(wheel_states)

        # 重置后清除上次的运动指令，防止车模基于旧的目标位置或速度继续运动
        # 将上一指令设为默认停车状态
        last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        command_lock = False
        uart3.write("Reset Position and Heading (Full State Reset). Stopping.\r\n")
        return

    # 检查是否为位置相关指令
    # 只要包含位置目标或相对移动，就视为位置指令
    is_pos_cmd = (
        "x" in cmd
        or "y" in cmd
        or "dx" in cmd
        or "dy" in cmd
        or "angle" in cmd
        or "d_angle" in cmd
    )

    # 如果处于锁定状态，且收到的是位置指令，则丢弃
    if command_lock and is_pos_cmd:
        uart3.write("Command Ignored (Locked)\r\n")
        return

    # 处理相对角度：如果存在 d_angle，将其转换为绝对 angle
    if "d_angle" in cmd:
        # 如果当前已是位置模式（last_cmd 有 angle），基于 heading_target
        # 如果当前是速度模式，heading_target 也会跟踪 est，所以 heading_target 一般是较好的基准
        # 但如果是从纯速度模式切换过来，heading_target 可能刚更新为 heading_est
        cmd["angle"] = heading_target + cmd["d_angle"]
        # 删除 d_angle，避免混淆（虽然保留也没事，因为 we prefer 'angle'）
        # cmd.pop("d_angle")

    # 处理相对位移：如果存在 dx 或 dy，将其转换为绝对 x, y
    if "dx" in cmd or "dy" in cmd:
        cmd["x"] = odometry.x + cmd.get("dx", 0.0)
        cmd["y"] = odometry.y + cmd.get("dy", 0.0)
        uart3.write(
            "Rel Move: dx=%.3f dy=%.3f -> x=%.3f y=%.3f\r\n"
            % (cmd.get("dx", 0.0), cmd.get("dy", 0.0), cmd["x"], cmd["y"])
        )

    last_cmd = cmd

    # 更新锁定状态
    # 如果是位置指令，加锁；如果是速度指令，解锁
    if is_pos_cmd:
        command_lock = True
    else:
        command_lock = False

    vx = cmd.get("vx", 0.0)
    vy = cmd.get("vy", 0.0)
    omega = cmd.get("omega", 0.0)

    # 注意: 这里计算仅用于串口反馈当前指令转换结果，实际控制循环中会重新计算 (尤其是在位置模式下)
    # 如果处于位置模式，这里的 vx vy 可能不是最终值
    if "x" in cmd or "y" in cmd:
        uart3.write("Pos Mode: x=%s, y=%s\r\n" % (str(cmd.get("x")), str(cmd.get("y"))))
        # 清除速度指令以免干扰
        if "vx" not in cmd:
            last_cmd["vx"] = None
        if "vy" not in cmd:
            last_cmd["vy"] = None
    else:
        vm, vl, vr = inverse_kinematics(vx, vy, omega)
        uart3.write(
            "OK vx=%.2f vy=%.2f om=%.2f ang=%s -> m=%.1f l=%.1f r=%.1f\r\n"
            % (
                vx,
                vy,
                omega,
                str(cmd.get("angle")),
                vm,
                vl,
                vr,
            )
        )


# 实例化 ticker 模块（周期中断）
uart3.write("Creating ticker...\r\n")
pit1 = ticker(1)
# 配置捕获编码器和 IMU 数据
capture_items = [state["encoder"] for state in wheel_states]
capture_items.append(imu)
# 将各模块挂载到 ticker 的 capture_list 中
pit1.capture_list(*capture_items)
# 绑定 ticker 回调函数
pit1.callback(pit_handler)

# 初始化 PID 控制器参数
init_pid()

# 以 TICK_MS 周期启动 ticker 模块
uart3.write("Starting ticker (%d ms)...\r\n" % TICK_MS)
pit1.start(TICK_MS)
uart3.write("Initialization complete. Control loop started.\r\n")

# 记录上一帧的时间 (微秒)
last_time_us = time.ticks_us()

while True:
    # 处理定时中断
    if pit_flag:
        # 定时器中断计数
        tick_count += 1
        # 切换 LED 状态
        led.toggle()

        # 计算真实的时间增量 dt_s (秒)
        # 即使循环被阻塞 (如串口打印)，积分也能保持准确
        current_time_us = time.ticks_us()
        dt_us = time.ticks_diff(current_time_us, last_time_us)
        last_time_us = current_time_us
        dt_s = dt_us / 1000000.0

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
        # imu_data indices: 3=Gx, 4=Gy, 5=Gz
        if imu_data:
            gx_raw = float(imu_data[3]) - imu_offsets[3]
            gy_raw = float(imu_data[4]) - imu_offsets[4]
            # Gyro Z is index 5
            gz_raw = float(imu_data[5]) - imu_offsets[5]
        else:
            gx_raw = gy_raw = gz_raw = 0.0

        # Convert raw LSB to rad/s
        # Scale is LSB / (deg/s), so val / Scale = deg/s
        # deg/s * (pi/180) = rad/s
        rad_scale = (math.pi / 180.0) / GYRO_SCALE
        gx = gx_raw * rad_scale
        gy = gy_raw * rad_scale
        gz = gz_raw * rad_scale

        # 更新四元数
        q_est.update(gx, gy, gz, dt_s)

        # 解算 Yaw 并进行解包 (Unwrap) 以获得连续角度
        curr_yaw_rad = q_est.to_euler_yaw()
        delta_yaw = curr_yaw_rad - last_yaw_rad

        # 处理角度突变 (Wrap around PI)
        if delta_yaw > math.pi:
            delta_yaw -= 2.0 * math.pi
        elif delta_yaw < -math.pi:
            delta_yaw += 2.0 * math.pi

        last_yaw_rad = curr_yaw_rad

        # 计算角速度 (deg/s) 用于 PD 控制的 D 项
        yaw_rate = gyro_lpf.update(gz * (180.0 / math.pi))

        # 为了兼容已有控制逻辑，继续使用 heading_est (deg)
        # 0. 获取轮速并更新里程计
        # 注意: state["filtered_speed"] 单位为 pulses/tick
        # 需要按照 wheel_states 顺序获取: m, l, r
        vm_pulse = wheel_states[0]["filtered_speed"]
        vl_pulse = wheel_states[1]["filtered_speed"]
        vr_pulse = wheel_states[2]["filtered_speed"]

        vm_mps = kinematics.velocity_pulses_to_m_s(vm_pulse, dt_s)
        vl_mps = kinematics.velocity_pulses_to_m_s(vl_pulse, dt_s)
        vr_mps = kinematics.velocity_pulses_to_m_s(vr_pulse, dt_s)

        # 计算机器人坐标系下的速度 (m/s)
        vx_rob_mps, vy_rob_mps, _ = kinematics.forward_kinematics(
            vm_mps, vl_mps, vr_mps
        )

        # 更新里程计 (使用 IMU 角度)
        odometry.update(vx_rob_mps, vy_rob_mps, math.radians(heading_est), dt_s)

        # 1. 姿态控制处理 (Angle / Omega)
        heading_est += math.degrees(delta_yaw)

        # 处理角速度
        # 优先级：Angle > Omega > Default (Hold)
        cmd_angle = last_cmd.get("angle")
        cmd_omega = last_cmd.get("omega")

        if cmd_angle is not None:
            # 位置模式 Position Mode
            heading_target = cmd_angle
            # 偏差为度
            yaw_err = heading_target - heading_est

            # 简单的 PD 控制产生角速度 omega (rad/s)
            # KP 作用于度，KD 作用于 deg/s
            omega_auto = YAW_KP * yaw_err - YAW_KD * yaw_rate
            omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)

        elif cmd_omega is not None:
            # 速度模式 Speed Mode
            omega_cmd = cmd_omega
            # 如果指令速度极低，则进入维持当前角度的 Hold 模式
            if abs(omega_cmd) < HOLD_SPEED_EPS:
                yaw_err = heading_target - heading_est
                omega_auto = clamp(
                    YAW_KP * yaw_err - YAW_KD * yaw_rate,
                    -AUTO_OMEGA_MAX,
                    AUTO_OMEGA_MAX,
                )
                omega_cmd = omega_auto
            else:
                heading_target = heading_est
        else:
            # 默认模式 (Hold)
            # 和速度模式 omega=0 行为一致
            yaw_err = heading_target - heading_est
            omega_auto = clamp(
                YAW_KP * yaw_err - YAW_KD * yaw_rate,
                -AUTO_OMEGA_MAX,
                AUTO_OMEGA_MAX,
            )
            omega_cmd = omega_auto

        # 2. XY 平面运动控制 (Position / Velocity)
        target_vx_cmd = 0.0
        target_vy_cmd = 0.0

        cmd_x = last_cmd.get("x")
        cmd_y = last_cmd.get("y")

        if cmd_x is not None or cmd_y is not None:
            # --- 位置控制模式 ---
            # 如果仅给定 x 或 y，另一个默认为 0
            t_x = cmd_x if cmd_x is not None else 0.0
            t_y = cmd_y if cmd_y is not None else 0.0

            err_x = t_x - odometry.x
            err_y = t_y - odometry.y

            # P 控制计算世界坐标系速度 (m/s)
            v_world_x = err_x * POS_KP
            v_world_y = err_y * POS_KP

            # 速度限幅
            v_speed = math.sqrt(v_world_x * v_world_x + v_world_y * v_world_y)
            if v_speed > POS_MAX_SPEED:
                scale = POS_MAX_SPEED / v_speed
                v_world_x *= scale
                v_world_y *= scale

            # 旋转到机器人坐标系
            # Robot X (Forward), Y (Left)
            # v_robot = R(-theta) * v_world
            t_rad = math.radians(heading_est)
            cos_t = math.cos(t_rad)
            sin_t = math.sin(t_rad)

            vx_rob_ctrl = v_world_x * cos_t + v_world_y * sin_t
            vy_rob_ctrl = -v_world_x * sin_t + v_world_y * cos_t

            # 转换为指令单位 (Pulses/Tick * 3) 以适配 inverse_kinematics
            # inverse_kinematics 内部会除以 3
            vx_pulses = kinematics.velocity_m_s_to_pulses(vx_rob_ctrl, dt_s)
            vy_pulses = kinematics.velocity_m_s_to_pulses(vy_rob_ctrl, dt_s)

            target_vx_cmd = vx_pulses * 3.0
            target_vy_cmd = vy_pulses * 3.0

        else:
            # --- 速度控制模式 ---
            # 直接使用指令值
            target_vx_cmd = float(last_cmd.get("vx", 0.0))
            target_vy_cmd = float(last_cmd.get("vy", 0.0))

        # 根据当前指令与自动回正叠加后的角速度解算目标轮速
        vm, vl, vr = inverse_kinematics(
            target_vx_cmd,
            target_vy_cmd,
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

        # 3. 检查锁定状态及目标是否达成
        if command_lock:
            # 检查角度误差
            angle_ok = True
            if last_cmd.get("angle") is not None:
                err_angle = abs(heading_target - heading_est)
                if err_angle > ANGLE_TOLERANCE:
                    angle_ok = False

            # 检查位置误差
            pos_ok = True
            if last_cmd.get("x") is not None or last_cmd.get("y") is not None:
                # 获取位置目标
                tx_chk = last_cmd.get("x")
                ty_chk = last_cmd.get("y")
                # 如果为 None 则取 0.0，与控制逻辑保持一致
                tx_val = tx_chk if tx_chk is not None else 0.0
                ty_val = ty_chk if ty_chk is not None else 0.0

                ex_val = tx_val - odometry.x
                ey_val = ty_val - odometry.y
                dist_err = math.sqrt(ex_val * ex_val + ey_val * ey_val)

                if dist_err > POS_TOLERANCE:
                    pos_ok = False

            # 如果所有目标都满足容差范围，则解锁
            if angle_ok and pos_ok:
                command_lock = False
                # uart3.write("Target Reached. Unlocked.\r\n")

        # 打印串口调试信息 (降频发送，避免阻塞)
        # 5ms * 20 = 100ms 刷新一次
        if tick_count % 20 == 0:
            # 发送状态数据到 uart6
            # 格式: quat_w,x,y,z | x,y (pos) | vx,vy (robot speed m/s)
            uart6.write(
                "{:.4f},{:.4f},{:.4f},{:.4f},{:.3f},{:.3f},{:.2f},{:.2f}\r\n".format(
                    q_est.w,
                    q_est.x,
                    q_est.y,
                    q_est.z,
                    odometry.x,
                    odometry.y,
                    vx_rob_mps,
                    vy_rob_mps,
                )
            )

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
