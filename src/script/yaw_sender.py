"""偏航角发送器脚本

@file src/script/yaw_sender.py
@brief 使用 IMU 陀螺仪进行四元数积分, 实时计算并发送车辆偏航角

@details 每个 5ms 控制周期采样一次陀螺仪, 进行四元数积分更新, 提取偏航角并以 "angle: xxx.xx" 格式发送到 UART3, 用于调试或外部监控系统
"""
from machine import UART
from seekfree import IMU963RX
from smartcar import ticker
from config import comm as comm_params
from config import motion as motion_params
from config import storage as storage_params
from utils.quaternion import Quaternion
import math
import time
import gc

# ===== 配置参数 (保持与 remote_control.py 一致) =====
# 控制周期, 单位毫秒
TICK_MS = getattr(motion_params, "TICK_MS")
# 陀螺仪比例因子, 单位 LSB / (deg/s), 用于原始值到角速度的转换
GYRO_SCALE = getattr(motion_params, "GYRO_SCALE")
# 陀螺仪零飘参数文件路径, 包含校准时测得的各轴偏移
GYRO_OFFSET_FILE = getattr(storage_params, "GYRO_OFFSET_FILE")
# 串口波特率
UART_BAUDRATE = getattr(comm_params, "UART_BAUDRATE")

# ===== 硬件初始化 =====
# UART3 用于输出调试数据
uart3 = UART(2)
uart3.init(UART_BAUDRATE)
uart3.write("IMU Yaw Sender Starting...\r\n")

# IMU 初始化
uart3.write("Initializing IMU...\r\n")
imu = IMU963RX()
# 获取 IMU 数据引用
imu_data = imu.get()

# ===== 状态变量初始化 =====
# 四元数估计姿态
q_est = Quaternion()
# 上次解算的 Yaw (弧度), 用于解包
last_yaw_rad = 0.0
# 估计的航向角 (累计角度, deg)
heading_est = 0.0
# 加载偏置参数
# -------------------------------------------------------------------------
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

# -------------------------------------------------------------------------
# 定时中断与循环控制
# -------------------------------------------------------------------------
pit_flag = False


def pit_handler(_tick):
    """Ticker 中断处理器:置位周期标志"""
    global pit_flag
    pit_flag = True


uart3.write("Creating ticker...\r\n")
pit1 = ticker(1)
# 将 IMU 挂载到 ticker 的 capture_list 中,实现后台自动采集
pit1.capture_list(imu)
pit1.callback(pit_handler)

uart3.write("Starting ticker (%d ms)...\r\n" % TICK_MS)
pit1.start(TICK_MS)

# 记录上一帧的时间 (微秒)
last_time_us = time.ticks_us()

# 主循环:每个周期计算并发送偏航角
while True:
    if pit_flag:
        # 计算时间增量 dt (秒)
        current_time_us = time.ticks_us()
        dt_us = time.ticks_diff(current_time_us, last_time_us)
        last_time_us = current_time_us
        dt_s = dt_us / 1000000.0

        # 获取陀螺仪数据并去除零飘
        if imu_data:
            # imu_data indices: 3=Gx, 4=Gy, 5=Gz
            gx_raw = float(imu_data[3]) - imu_offsets[3]
            gy_raw = float(imu_data[4]) - imu_offsets[4]
            gz_raw = float(imu_data[5]) - imu_offsets[5]
        else:
            gx_raw = gy_raw = gz_raw = 0.0

        # 将原始数据转换为弧度/秒 (rad/s)
        # raw / Scale = deg/s
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

        # 累积航向角 (Degrees)
        heading_est += math.degrees(delta_yaw)

        # 通过 UART3 发送解算的偏航角
        # 格式: "angle: xxx.xx"
        uart3.write("angle: {:.2f}\r\n".format(heading_est))

        pit_flag = False

    gc.collect()
