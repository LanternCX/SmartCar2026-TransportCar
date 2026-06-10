"""运动配置

@file src/config/motion.py
@brief 速度、角速度、绕行和位置控制相关参数

@details 配置项按使用频率排序, 便于优先查看常调的运动参数
"""

# 最小直行搬运基础速度
TRANSPORT_FORWARD_SPEED = 3.0
# 搬运收尾阶段主辅车第二段保留位置同步时的默认位移, 单位米
TRANSPORT_CLEAR_STEP_DISTANCE_M = 0.0
# 搬运收尾阶段主车后退距离, 单位米
TRANSPORT_CLEAR_RETREAT_DISTANCE_M = 0.10
# 搬运收尾阶段主车后退最大速度
TRANSPORT_CLEAR_RETREAT_MAX_SPEED = 3.0
# 主车回库后退找黄线的固定速度
MASTER_RETURN_GARAGE_RETREAT_SPEED = -2.0
# 主车回库黄线段固定左移速度
MASTER_RETURN_GARAGE_LEFT_SPEED = -3.0
# 辅车回库黄线段固定左移速度
ASSISTANT_RETURN_GARAGE_LEFT_SPEED = -3.0
# 状态收尾判定时三轮接近静止的默认轮速阈值, 单位脉冲/控制拍
MOTION_STOP_SPEED_THRESHOLD = 0.5
# 状态收尾判定时三轮接近静止需要连续满足的默认拍数
MOTION_STOP_CONFIRM_TICKS = 3
# 全向轮轮径, 单位米, 用于编码器脉冲与物理距离换算
WHEEL_DIAMETER_M = 0.038
# 位置控制最大速度, 单位 m/s, 在 P 控制中作为饱和限幅
POS_MAX_SPEED = 0.05
# 位置控制比例系数, 单位 Speed (m/s) / Error (m), 决定偏差如何转换为速度指令
POS_KP = 2.0
# 位置锁定容差, 单位米, 位置偏差小于此值时认为已到达目标
POS_TOLERANCE = 0.05
# 角度锁定容差, 单位度, 角度偏差小于此值时认为已到达目标
ANGLE_TOLERANCE = 5.0
# 陀螺仪低通滤波系数, 范围 0 ~ 1
GYRO_LPF_ALPHA = 0.2
# 偏航角位置环 P 增益, 单位为 ω / rad
YAW_KP = 0.16
# 偏航角位置环 I 增益, 用于消除稳态偏差
YAW_KI = 0.1
# 偏航角位置环 D 增益, 用于阻尼控制
YAW_KD = 0.008
# 积分项饱和限幅, 防止积分超调
YAW_I_MAX = 100.0
# 朝向保持最大角速度, 对应轮速分量
AUTO_OMEGA_MAX = 15.0
# 朝向跳转最大角速度, 对应轮速分量
HEADING_TRANSITION_OMEGA_MAX = 1.50
# 绕行阶段最大角速度, 对应轮速分量
ORBIT_AUTO_OMEGA_MAX = 1
# 保持模式速度阈值, 当目标轮速小于此值时判定为保持模式
HOLD_SPEED_EPS = 0.01
# 主车绕行的绝对目标角度增量, 单位度
MASTER_ORBIT_TARGET_DEG = 180
# 主车绕行半径倍率, 1.0 表示共享底盘单位半径基准
MASTER_ORBIT_RADIUS_SCALE = 3.0
# 主车回到寻找构型前的原地回身角度, 单位度
MASTER_TURN_BACK_DELTA_DEG = 180
# 主车搬运收尾回身阶段放行角度容差, 单位度
MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG = 8.0
# 辅车绕行的绝对目标角度, 单位度
ASSISTANT_ORBIT_TARGET_DEG = 0
# 辅车绕行半径倍率, 1.0 表示共享底盘单位半径基准
ASSISTANT_ORBIT_RADIUS_SCALE = 3.0
# 三轮速度环 PID 参数映射
PID_MAP = {
    "m": (100, 500, 1),
    "l": (100, 500, 1),
    "r": (100, 500, 1),
}
# 主控制循环周期, 单位毫秒
TICK_MS = 5
# 启用的轮子集合, 用于调试时选择性激活特定轮子
ACTIVE_WHEELS = ("m", "l", "r")
# 陀螺仪比例因子, 单位 LSB / (deg/s), 用于原始数值到角速度的转换
GYRO_SCALE = 14.285714285714286
# 角速度 Z 轴在 IMU 返回数组中的索引位置
GYRO_AXIS_Z = 5
