"""配置管理模块.

集中存放搬运车控制的所有可调参数,包括控制周期、PWM 限制、
运动学参数、PID 增益、陀螺仪滤波、位置控制等.
"""

# 控制周期 (ms)
TICK_MS = 5
# PWM 占空比上限
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

# 视觉状态机参数
VISION_OBSERVATION_TIMEOUT_MS = 120
VISION_TARGET_CENTER_X_PX = 160.0
VISION_TARGET_BOTTOM_PX = 240.0
VISION_ANGLE_KP = 0.3
VISION_DIST_KP = 0.0005
VISION_DX_KP = 0.0005
VISION_PUSH_DX_KP = 0.0005
VISION_PUSH_DY_M = 0.2
VISION_PUSH_DISTANCE_M = 0.2
VISION_PUSH_ANGLE_DEG = -90.0
VISION_ANGLE_DEADZONE_PX = 15.0
VISION_ANGLE_REENTRY_PX = 15.0
VISION_DIST_DEADZONE_PX = 15.0
VISION_DX_DEADZONE_PX = 10.0
VISION_HEADING_TOLERANCE_DEG = 10.0
VISION_STABLE_FRAMES = 2
VISION_MAX_DX_M = 0.1
VISION_MAX_DY_M = 0.2
VISION_MAX_D_ANGLE_DEG = 45.0
VISION_DONE_HOLD_MS = 2000

# 启用的轮子(调试用)
ACTIVE_WHEELS = ("m", "l", "r")

# 陀螺仪低通滤波系数
GYRO_LPF_ALPHA = 0.2
# 陀螺仪比例因子 (LSB / (deg/s))
GYRO_SCALE = 16.384
# 角速度轴索引(Z 轴为索引 5)
GYRO_AXIS_Z = 5
# 偏航角位置 PID 参数(单位为度)
YAW_KP = 0.16
YAW_KI = 0.1
YAW_KD = 0.008
# 积分项限幅
YAW_I_MAX = 100.0
# 自动回正最大角速度(对应轮速分量)
AUTO_OMEGA_MAX = 15.0
# 保持模式速度阈值
HOLD_SPEED_EPS = 0.01

# 系统辨识参数文件路径
IDENT_RESULTS_FILE = "/flash/ident_params.txt"
# 陀螺仪零飘文件路径
GYRO_OFFSET_FILE = "/flash/gyro_offset.txt"

# 三轮速度环参数表 {轮子名: (P, D, P2)}
PID_MAP = {
    "m": (100, 500, 1),
    "l": (100, 500, 1),
    "r": (100, 500, 1),
}

# 日志等级定义
LOG_TRACE = 10
LOG_DEBUG = 20
LOG_INFO = 30
LOG_WARN = 40
LOG_ERROR = 50
LOG_FATAL = 60

# 日志默认配置
LOG_LEVEL_DEFAULT = LOG_INFO
LOG_FILTER_MODE_DEFAULT = "off"
LOG_FILTER_MODULES_DEFAULT = ()
