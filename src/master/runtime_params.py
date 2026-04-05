"""主车当前主线参数入口.

@file src/master/runtime_params.py

负责集中声明主车入口与底座主链共享的节拍、跟随和航向保持参数。
运行链会配合 `gyro_offset.txt` 与 `ident_params.txt` 中的校准结果一起使用这些参数。
"""

# 视觉跟随阶段使用的目标有效期与中心死区, 单位分别为 ms 和 px
FOLLOW_TIMEOUT_MS = 150
FOLLOW_CONTROL_KP_X = 1.0
FOLLOW_CONTROL_KP_Y = 1.0
FOLLOW_CENTER_DEADZONE_PX = 8.0

# 主循环节拍与速度估计窗口配置
CONTROL_TICK_MS = 5
LONG_WINDOW = 30
SHORT_WINDOW = 8

# 电机输出边界, 单位 duty
FOLLOW_OUTPUT_LIMIT = 10000
MAX_DUTY = 10000

# 三路轮速环 PID 参数表, 顺序为 kp、ki、kd
PID_MAP = {
    "m": (100, 500, 1),
    "l": (100, 500, 1),
    "r": (100, 500, 1),
}

# 轮速与角速度滤波配置
SPEED_FILTER_WINDOW = 5
SPEED_DIFF_MAX_DELTA = 5.0
GYRO_LPF_ALPHA = 0.2

# 航向保持控制参数, 其中角速度上限单位为 deg/s
YAW_KP = 0.2
YAW_KI = 0.0
YAW_KD = 0.05
YAW_I_MAX = 100.0
AUTO_OMEGA_MAX = 15.0
HOLD_SPEED_EPS = 0.01
