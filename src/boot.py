# 本示例程序演示如何通过 boot.py 文件进行 soft-boot 控制
# 使用 RT1021-MicroPython 核心板搭配对应拓展学习板的拨码开关控制

# 示例程序运行效果为复位后执行本文件 通过 D8 电平状态决定是否跳转执行 user_main.py

# 从 machine 库包含所有内容
from machine import *

# 包含 gc 与 time 类
import gc
import time

# 上电启动时间延时
time.sleep_ms(50)
# 选择学习板上的一号拨码开关作为启动选择开关
# D8 代表 PID 参数识别程序 打开状态为 0 关闭状态为 1
pid_ident = Pin("D8", Pin.IN, pull=Pin.PULL_UP_47K)
# D9 代表陀螺仪校准程序 打开状态为 0 关闭状态为 1
gyro_cal = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)

# 0 1 代表执行 PID 参数识别程序
if pid_ident.value() == 0 and gyro_cal.value() == 1:
    try:
        os.chdir("/flash")
        execfile("script/pid_identify.py")
    except:
        print("File not found.")

# 1 0 代表执行陀螺仪校准程序
if pid_ident.value() == 1 and gyro_cal.value() == 0:
    try:
        os.chdir("/flash")
        execfile("script/calibrate_gyro.py")
    except:
        print("File not found.")

# 1 1 代表执行遥控器控制程序
if pid_ident.value() == 1 and gyro_cal.value() == 1:
    try:
        os.chdir("/flash")
        execfile("script/remote_control.py")
    except:
        print("File not found.")
