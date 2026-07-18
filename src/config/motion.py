"""运动配置

@file src/config/motion.py
@brief 速度、角速度、绕行和位置控制相关参数

@details 配置项按使用频率排序, 便于优先查看常调的运动参数
"""

# 最小直行搬运基础速度
TRANSPORT_FORWARD_SPEED = 9.0
# 主车推行速度从零爬升到基础速度的时间, 单位秒
MASTER_TRANSPORT_ACCEL_TIME_S = 1
# 辅车推行速度从零爬升到本车基础速度的时间, 单位秒
ASSISTANT_TRANSPORT_ACCEL_TIME_S = 2
# 搬运收尾阶段主辅车第二段保留位置同步时的默认位移, 单位米
TRANSPORT_CLEAR_STEP_DISTANCE_M = 0.0
# 搬运收尾阶段主车后退距离, 单位米
TRANSPORT_CLEAR_RETREAT_DISTANCE_M = 0.10
# 搬运收尾阶段主车后退最大速度
TRANSPORT_CLEAR_RETREAT_MAX_SPEED = 6.0
# 状态收尾判定时三轮接近静止的默认轮速阈值, 单位脉冲/控制拍
MOTION_STOP_SPEED_THRESHOLD = 1
# 状态收尾判定时三轮接近静止需要连续满足的默认拍数
MOTION_STOP_CONFIRM_TICKS = 1
# 全向轮轮径, 单位米, 用于编码器脉冲与物理距离换算
WHEEL_DIAMETER_M = 0.038
# 主车里程计距离补偿系数, 格式为 (x, y), 对应车体系右移与前进
MASTER_ODOMETRY_DISTANCE_SCALE = (0.65723685, 0.648589)
# 辅车里程计距离补偿系数, 格式为 (x, y), 对应车体系右移与前进
ASSISTANT_ODOMETRY_DISTANCE_SCALE = (0.66205803, 0.73290557)
# 蚂蚁搬家场地尺寸, 单位米, 格式为 (x, y)
FIELD_SIZE_M = (3.2, 2.4)
# 主车发车坐标, 单位米, 格式为 (x, y)
MASTER_START_POSITION_M = (0.30, 0.0)
# 辅车发车坐标, 单位米, 格式为 (x, y)
ASSISTANT_START_POSITION_M = (0.10, 0.0)
# 出库第一段世界系 Y 目标, 单位米
STARTUP_TARGET_Y_M = 0.70
# 是否使用决赛搬运目标边配置, False 时初赛统一搬运到底边
IS_FINAL_ROUND = False
# 物体目标边配置, 编号依次为红色、蓝色、棕色、白色、网球
TRANSPORT_OBJECT_TARGET_EDGE = (
    {
        1: "left",
        2: "left",
        3: "right",
        4: "right",
        5: "top",
    }
    if IS_FINAL_ROUND
    else {-1: "bottom"}
)
# 位置控制最大命令速度, 单位脉冲/控制拍
POS_MAX_SPEED = 5.0
# 位置控制比例系数, 单位 Speed (m/s) / Error (m), 决定偏差如何转换为速度指令
POS_KP = 5.0
# 位置锁定容差, 单位米, 位置偏差小于此值时认为已到达目标
POS_TOLERANCE = 0.06
# 角度锁定容差, 单位度, 角度偏差小于此值时认为已到达目标
ANGLE_TOLERANCE = 8.0
# 陀螺仪低通滤波系数, 范围 0 ~ 1
GYRO_LPF_ALPHA = 0.2
# 偏航角位置环 P 增益, 单位为 ω / rad
YAW_KP = 0.16
# 偏航角位置环 I 增益, 用于消除稳态偏差
YAW_KI = 0.5
# 偏航角位置环 D 增益, 用于阻尼控制
YAW_KD = 0.008
# 积分项饱和限幅, 防止积分超调
YAW_I_MAX = 100.0
# 朝向保持最大角速度, 对应轮速分量
AUTO_OMEGA_MAX = 15.0
# 朝向跳转最大角速度, 对应轮速分量
HEADING_TRANSITION_OMEGA_MAX = 4
# 绕行阶段最大角速度, 对应轮速分量
ORBIT_AUTO_OMEGA_MAX = 1
# 绕行角度进入容差后需要连续保持的控制拍数
ORBIT_ANGLE_CONFIRM_TICKS = 3
# 保持模式速度阈值, 当目标轮速小于此值时判定为保持模式
HOLD_SPEED_EPS = 0.01
# 主车绕行半径倍率, 1.0 表示共享底盘单位半径基准
MASTER_ORBIT_RADIUS_SCALE = 2.5
# 主车实际绕行角小于该值时进入辅车绕行避让流程, 单位度
MASTER_ORBIT_AVOID_TRIGGER_DEG = 60
# 主车为辅车让出绕行视野时相对搬运方向的目标偏角, 单位度
MASTER_ORBIT_AVOID_HEADING_DEG = 90
# 主车在避让朝向下沿车体前方侧推物体的距离, 单位米
MASTER_ORBIT_AVOID_PUSH_DISTANCE_M = 0.20
# 绕行定位使用的车辆参考点到物体中心固定半径, 单位米
ORBIT_POSITION_RADIUS_M = 0.13
# 主动原地转向时车辆参考点绕旋转中心的半径, 单位米
IN_PLACE_ROTATION_RADIUS_M = 0.08
# 障碍区间两端用于生成避障触发范围的余量, 单位米
TRANSPORT_OBSTACLE_MARGIN_M = 0.45
# 回库规划中边线障碍向场内延伸的物理深度, 单位米
RETURN_GARAGE_OBSTACLE_DEPTH_M = 0.50
# 辅车搬运到边时车辆参考点相对场地边界的内缩距离, 单位米
ASSISTANT_TRANSPORT_EDGE_INSET_M = 0.08
# 主车回库第一阶段至少后退的距离, 单位米
MASTER_RETURN_GARAGE_EXTRA_RETREAT_M = 0.40
# 辅车回库第一阶段至少后退的距离, 单位米
ASSISTANT_RETURN_GARAGE_EXTRA_RETREAT_M = 0.30
# 主车回到寻找构型前的原地回身角度, 单位度
MASTER_TURN_BACK_DELTA_DEG = 180
# 主车搬运收尾回身阶段放行角度容差, 单位度
MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG = 8.0
# 辅车绕行半径倍率, 1.0 表示共享底盘单位半径基准
ASSISTANT_ORBIT_RADIUS_SCALE = 2.5
# 三轮速度环 PID 参数映射
PID_MAP = {
    "m": (100, 500, 1),
    "l": (100, 500, 1),
    "r": (100, 500, 1),
}
# 底盘控制周期, 单位毫秒
TICK_MS = 5
# 角色状态机决策周期, 单位毫秒
ROLE_STEP_MS = 100
# 视觉运动输入周期, 单位毫秒
MOTION_INPUT_STEP_MS = 15
# 启用的轮子集合, 用于调试时选择性激活特定轮子
ACTIVE_WHEELS = ("m", "l", "r")
# 陀螺仪比例因子, 单位 LSB / (deg/s), 用于原始数值到角速度的转换
GYRO_SCALE = 14.285714285714286
# 角速度 Z 轴在 IMU 返回数组中的索引位置
GYRO_AXIS_Z = 5
