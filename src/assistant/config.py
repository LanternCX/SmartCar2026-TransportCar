"""辅车配置与已确认硬件事实.

@file src/assistant/config.py
"""

UART_BAUDRATE = 115200
# 当前辅车保留 UART3 通用链路, 并新增 UART6 视觉跟随输入
UART_IDS = {
    "uart3": 2,
    "uart6": 5,
}
# IMU 原始角速度换算为度每秒时使用的量程比例
GYRO_SCALE = 16.384
# 零漂校准脚本把 6 轴偏置持久化到板载 flash 的固定位置
GYRO_OFFSET_FILE = "/flash/gyro_offset.txt"
# 电机辨识脚本把每轮增益和时间常数写回这里
IDENT_RESULTS_FILE = "/flash/ident_params.txt"
