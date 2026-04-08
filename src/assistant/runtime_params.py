"""集中提供辅车主链装配时要读取的控制、滤波和安全参数, 上游由入口和运行时统一引用。

它对外职责是作为稳定参数源, 让应用编排、周期推进和安全停机共用同一套阈值与配置。

@file src/assistant/runtime_params.py
"""

# 主车命令超时停机阈值, 单位毫秒
FOLLOW_TIMEOUT_MS = 150
# 主循环控制周期, 单位毫秒
CONTROL_TICK_MS = 5
# 轮速长窗回归长度, 用于平滑辨识和控制测速
LONG_WINDOW = 30
# 轮速短窗回归长度, 用于兼顾响应速度
SHORT_WINDOW = 8
# 跟随和平移指令在运行时的统一输出上限
FOLLOW_OUTPUT_LIMIT = 10000
# 电机 PWM 占空比上限
MAX_DUTY = 10000
# 三路轮速 PID 参数表, 按中轮/左轮/右轮分配
PID_MAP = {
    "m": (100, 500, 1),
    "l": (100, 500, 1),
    "r": (100, 500, 1),
}
# 轮速滤波基础窗口长度
SPEED_FILTER_WINDOW = 5
# 相邻测速样本允许的最大跳变
SPEED_DIFF_MAX_DELTA = 5.0
# 航向角速度低通滤波系数
GYRO_LPF_ALPHA = 0.2
# 航向保持 PID 比例项
YAW_KP = 0.08
# 航向保持 PID 积分项
YAW_KI = 0.001
# 航向保持 PID 微分项
YAW_KD = 0.01
# 航向保持积分限幅
YAW_I_MAX = 100.0
# 自动航向保持允许输出的最大角速度
AUTO_OMEGA_MAX = 15.0
# 低于该角速度阈值时回到自动航向保持
HOLD_SPEED_EPS = 0.01
# 跟随位置控制比例项
FOLLOW_POSITION_KP = 1.0
# 跟随位置控制最大平移速度
FOLLOW_POSITION_MAX_SPEED = 3.0
