"""IMU 陀螺仪零飘校准脚本

@file src/script/calibrate_gyro.py
@brief 通过静止测量来校准 IMU 的陀螺仪和加速度计零飘

@details 脚本采集 2000 个样本, 计算各轴传感器的平均值作为零飘偏移, 保存至 /flash/gyro_offset.txt, 用于后续在线控制中消除传感器系统误差

操作步骤:
1. 启动脚本
2. 平放车辆, 保持绝对静止 (约 20 秒)
3. 脚本自动采集 2000 个样本并计算平均零飘
4. 结果保存在 Flash 中, LED 持续闪烁表示完成
"""
from machine import Pin
from seekfree import IMU660RX
import time

# LED 指示灯, 用于校准进度提示
led = Pin("C4", Pin.OUT, value=True)

# IMU 初始化
imu = IMU660RX()
# 陀螺仪 Z 轴在返回数据中的索引位置
GYRO_AXIS_Z = 5
# 采样样本数, 用于计算平均值的稳定性
SAMPLE_COUNT = 2000
# 零飘偏移文件保存路径
OFFSET_FILE = "/flash/gyro_offset.txt"


print("=" * 40)
print("开始IMU六轴零飘校准 (IMU 6-Axis Calibration)")
print("请平放车辆并保持绝对静止!")
print("KEEP THE CAR STILL AND FLAT!")
print("=" * 40)

# 闪烁 LED 提示准备开始
for _ in range(10):
    led.toggle()
    time.sleep_ms(100)

print(f"正在采集 {SAMPLE_COUNT} 个样本...")

# [AccX, AccY, AccZ, GyroX, GyroY, GyroZ]
totals = [0.0] * 6
start_time = time.ticks_ms()

for i in range(SAMPLE_COUNT):
    # 立即读取一次数据
    imu.read()
    data = imu.get()

    for axis in range(6):
        totals[axis] += float(data[axis])

    if i % 200 == 0:
        print(f"进度: {i}/{SAMPLE_COUNT}")
        led.toggle()

    time.sleep_ms(2)

end_time = time.ticks_ms()
duration = (end_time - start_time) / 1000.0

means = [t / SAMPLE_COUNT for t in totals]
print("-" * 40)
print(f"采集完成,耗时 {duration:.2f} 秒")
print("平均值 (Offsets):")
print(f"Acc : {means[0]:.2f}, {means[1]:.2f}, {means[2]:.2f}")
print(f"Gyro: {means[3]:.2f}, {means[4]:.2f}, {means[5]:.2f}")

# 保存格式: acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z
offset_str = ",".join([f"{v:.4f}" for v in means])

try:
    with open(OFFSET_FILE, "w") as f:
        f.write(offset_str)
    print(f"成功保存校准参数到: {OFFSET_FILE}")
except Exception as e:
    print(f"保存文件失败: {e}")

# 提示完成 (持续闪烁)
while True:
    led.toggle()
    time.sleep_ms(500)
