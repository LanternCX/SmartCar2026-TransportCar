"""主车配置与已确认硬件事实.

@file src/master/config.py
"""

UART_BAUDRATE = 115200
UART_IDS = {
    "uart3": 2,
    "uart6": 5,
    "uart8": 7,
}
GYRO_SCALE = 16.384
# `gyro_offset.txt` 保存主车 IMU 六轴零漂结果, 板端启动时按这个路径回读校准值
GYRO_OFFSET_FILE = "/flash/gyro_offset.txt"
# `ident_params.txt` 保存电机辨识得到的增益与时间常数, 速度环初始化时按这个路径装载
IDENT_RESULTS_FILE = "/flash/ident_params.txt"
