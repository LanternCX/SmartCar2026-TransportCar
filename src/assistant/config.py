"""辅车配置与已确认硬件事实.

@file src/assistant/config.py
"""

UART_BAUDRATE = 115200
UART_IDS = {
    "uart3": 2,
}
GYRO_SCALE = 16.384
GYRO_OFFSET_FILE = "/flash/gyro_offset.txt"
IDENT_RESULTS_FILE = "/flash/ident_params.txt"
