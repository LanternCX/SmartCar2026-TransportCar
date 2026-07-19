"""持久化配置

@file src/config/storage.py
@brief 文件路径与持久化相关参数
"""

# 系统辨识参数的保存路径, 用于存储轮子的增益和时间常数
IDENT_RESULTS_FILE = "/flash/storage/ident_params.txt"
# 陀螺仪零飘偏移的保存路径, 用于存储静止时的陀螺仪平均值
GYRO_OFFSET_FILE = "/flash/storage/gyro_offset.txt"
# 场地障碍配置路径
OBSTACLE_CONFIG_FILE = "/flash/storage/obstacles.txt"
