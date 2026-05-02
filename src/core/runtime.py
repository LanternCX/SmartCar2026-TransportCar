"""
@file runtime.py
@brief 搬运车控制单例封装

@details 提供搬运车的核心控制逻辑, 包括硬件初始化、运动学计算、PID 控制、短包输入处理等功能
"""

import gc
import math
import time

from machine import Pin
from control.wheel import build_wheel_state
from control.pid_controller import SpeedPIDController, PositionalPIDController
from control.pid_math import clamp, reset_pi_state
from control.kinematics import OmniKinematics, Odometry
from filters.lowpass_filter import LowPassFilter
from filters.spike_filter import SpikeMedianFilter
from filters.diff_limit_filter import DiffLimitFilter
from utils.quaternion import Quaternion
from utils.startup_log import startup_log
from config import params as _params
from hardware.uart_bus import create_uart3, create_uart8
from hardware.motors import create_motors
from hardware.encoders import create_encoders
from hardware.imu import create_imu
from storage.param_manager import load_ident_lookup, load_gyro_offsets
from protocol.packet import parse_short_packet


TICK_MS = getattr(_params, "TICK_MS")
MAX_DUTY = getattr(_params, "MAX_DUTY")
TARGET_SPEED_MAX = getattr(_params, "TARGET_SPEED_MAX")
POS_MAX_SPEED = getattr(_params, "POS_MAX_SPEED")
POS_KP = getattr(_params, "POS_KP")
POS_TOLERANCE = getattr(_params, "POS_TOLERANCE")
ANGLE_TOLERANCE = getattr(_params, "ANGLE_TOLERANCE")
ACTIVE_WHEELS = getattr(_params, "ACTIVE_WHEELS")
GYRO_LPF_ALPHA = getattr(_params, "GYRO_LPF_ALPHA")
GYRO_SCALE = getattr(_params, "GYRO_SCALE")
YAW_KP = getattr(_params, "YAW_KP")
YAW_KI = getattr(_params, "YAW_KI")
YAW_KD = getattr(_params, "YAW_KD")
YAW_I_MAX = getattr(_params, "YAW_I_MAX")
AUTO_OMEGA_MAX = getattr(_params, "AUTO_OMEGA_MAX")
HOLD_SPEED_EPS = getattr(_params, "HOLD_SPEED_EPS")
IDENT_RESULTS_FILE = getattr(_params, "IDENT_RESULTS_FILE")
GYRO_OFFSET_FILE = getattr(_params, "GYRO_OFFSET_FILE")
PID_MAP = getattr(_params, "PID_MAP")


class _NullImu:
    """
    @brief 诊断模式下使用的空 IMU 占位类, 模拟真实 IMU 接口

    @details 在诊断或模拟环境下替代真实 IMU 硬件, 避免硬件依赖, 便于离线测试
            实现与真实 IMU 相同的 get() 接口, 但始终返回全零数据
    """

    def get(self):
        """
        @brief 获取模拟的六轴传感器数据

        @return 包含 6 个 0.0 的列表, 格式为 [ax, ay, az, gx, gy, gz]
                分别对应加速度三轴和陀螺仪三轴(单位: g 和 deg/s)
        """
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class _NullEncoder:
    """
    @brief 诊断模式下使用的空编码器占位类, 模拟真实编码器接口

    @details 在诊断或模拟环境下替代真实编码器硬件, 避免硬件依赖, 便于离线测试
            实现与真实编码器相同的 get() 接口, 但始终返回 0 脉冲
    """

    def get(self):
        """
        @brief 获取模拟的编码器脉冲数

        @return 固定返回 0.0, 表示无脉冲输入
        """
        return 0.0


class _NullMotor:
    """
    @brief 诊断模式下使用的空电机占位类, 模拟真实电机接口

    @details 在诊断或模拟环境下替代真实电机硬件, 仅记录占空比指令而不触发
            真实硬件输出, 便于离线测试和算法验证
    """

    def __init__(self):
        """
        @brief 初始化空电机实例

        @details 初始化占空比记录值为 0
        """
        self.last_duty = 0

    def duty(self, value):
        """
        @brief 设置电机占空比(模拟)

        @details 仅记录占空比值到 last_duty 供诊断读取, 不触发真实硬件输出

        @param value 目标占空比值(-MAX_DUTY ~ +MAX_DUTY), 会被转换为整数存储
        """
        self.last_duty = int(value)


def _create_null_encoders():
    """
    @brief 为诊断模式构造三轮空编码器集合

    @details 创建三个 _NullEncoder 实例, 分别对应 Y 型三轮的三个轮子
    - "m": 中轮(后方中心)
    - "l": 左轮(前左方)
    - "r": 右轮(前右方)

    @return 包含三个 _NullEncoder 实例的字典, 键为轮子标识符
    """
    return {"m": _NullEncoder(), "l": _NullEncoder(), "r": _NullEncoder()}


def _create_null_motors():
    """
    @brief 为诊断模式构造三轮空电机集合

    @details 创建三个 _NullMotor 实例, 分别对应 Y 型三轮的三个轮子
    - "m": 中轮(后方中心)
    - "l": 左轮(前左方)
    - "r": 右轮(前右方)

    @return 包含三个 _NullMotor 实例的字典, 键为轮子标识符
    """
    return {"m": _NullMotor(), "l": _NullMotor(), "r": _NullMotor()}


class TransportCar:
    """
    @brief 搬运车核心控制单例

    @details 集成硬件管理、运动学计算、PID 控制和结构化控制入口
            负责协调电机、编码器、IMU 等硬件资源, 实现周期性控制循环

    @note 主要职责
    - 硬件初始化与资源管理: 电机、编码器、IMU、串口等
    - 周期性控制循环(TICK_MS=5ms 周期)
    - 速度环闭环控制与逆运动学变换
    - 位置锁定与偏航角 PID 控制
    - 串口短包解析和结构化速度写入

    使用示例:
    @code
        car = TransportCar()
        car.set_ticker(ticker_obj)  # 注册 5ms 周期中断
        while True:
            if not car.step():
                break  # 检测到急停或其他致命错误
    @endcode
    """

    def __init__(self, diagnostic_mode=False):
        """
        @brief 初始化搬运车所有组件

        @details 完成硬件初始化、滤波器和状态变量的构造
                包括电机、编码器、IMU、运动学、PID 控制器、串口等

        @param diagnostic_mode 是否启用诊断模式.若为 True, 则跳过真实硬件初始化
                               使用空占位对象替代 IMU、电机和编码器
        """
        self.diagnostic_mode = bool(diagnostic_mode)
        startup_log("transport_car", "init start")

        # 硬件接口: 板载 LED 用于运行状态指示, switch2 为硬件紧急停止按钮
        self.led = Pin("C4", Pin.OUT, value=True)
        self.switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
        self.switch2_init = self.switch2.value()

        # 串口通信接口: uart3 接收上位机速度短包, uart8 用于主辅设备间通信
        self.uart3 = create_uart3()
        self.uart8 = create_uart8()
        startup_log("transport_car", "uart ready")

        # IMU 传感器(陀螺仪+加速度计), 用于姿态估计与航向角反馈
        # 诊断模式下使用空占位对象避免硬件依赖
        if self.diagnostic_mode:
            startup_log("transport_car", "diagnostic mode skip IMU init")
            self.imu = _NullImu()
        else:
            startup_log("transport_car", "IMU init start")
            self.imu = create_imu()
            startup_log("transport_car", "IMU ready")
        self.imu_data = self.imu.get()

        # 姿态估计与陀螺仪滤波状态
        # @details gyro_lpf: 陀螺仪角速度低通滤波器, 平滑原始测量噪声
        #          heading_est: 当前航向角(度), 通过四元数积分与陀螺仪融合得到
        #          q_est: 四元数估计值, 积分陀螺仪角速度以计算精确航向
        #          last_yaw_rad: 上一周期航向角(弧度), 用于计算航向差分
        self.gyro_lpf = LowPassFilter(alpha=GYRO_LPF_ALPHA, initial=0.0)
        self.heading_est = 0.0
        self.q_est = Quaternion()
        self.last_yaw_rad = 0.0

        # 偏航角位置式 PID 控制器, 输出目标角速度以追踪目标航向
        # @details 使用位置式 PID 以支持 I 项积分防饱和(YAW_I_MAX)
        #          输出限幅为 ±AUTO_OMEGA_MAX, 防止过度转向
        #          yaw_integral: 调试辅助字段, 记录积分项当前值
        self.yaw_pid = PositionalPIDController(
            output_limit=AUTO_OMEGA_MAX, integral_limit=YAW_I_MAX
        )
        self.yaw_pid.set_gains(YAW_KP, YAW_KI, 0.0)
        self.yaw_integral = 0.0

        # 运动学与里程计
        # @details kinematics: Y 型三轮全向车的正逆运动学变换
        #          odometry: 积分世界系速度, 记录车体当前位置 (x, y)
        self.kinematics = OmniKinematics()
        self.odometry = Odometry()

        # 航向角目标值(度), 由角度控制目标或当前航向初始化, 用于偏航 PID 反馈
        self.heading_target = 0.0

        # 电机和编码器: 三轮独立驱动与速度反馈
        # 诊断模式下使用空占位对象避免硬件依赖
        if self.diagnostic_mode:
            startup_log("transport_car", "diagnostic mode skip motor/encoder init")
            self.motors = _create_null_motors()
            self.encoders = _create_null_encoders()
        else:
            startup_log("transport_car", "motor/encoder init start")
            self.motors = create_motors()
            self.encoders = create_encoders()
            startup_log("transport_car", "motor/encoder ready")

        # 速度环 PID 参数: 加载电机辨识结果, 包括增益和时间常数
        # 用于每轮独立的速度环整定, 从文件 IDENT_RESULTS_FILE 读取
        startup_log("transport_car", "loading calibration data")
        self.ident_lookup = load_ident_lookup(IDENT_RESULTS_FILE)

        # 陀螺仪零偏校正: 从文件 GYRO_OFFSET_FILE 加载, 用于抵消硬件漂移
        self.imu_offsets = load_gyro_offsets(
            GYRO_OFFSET_FILE,
            logger=lambda msg: startup_log("transport_car", msg),
        )

        # 轮组状态构造: 每轮包含编码器、电机、滤波器、PID 控制器
        # @details wheel_states 是三个字典列表, 存储 [m, l, r] 三轮的完整状态
        #          state["name"]: 轮子标识符("m"、"l"、"r")
        #          state["encoder"]: 编码器接口, 提供原始脉冲
        #          state["motor"]: 电机接口, 设置占空比输出
        #          state["controller"]: SpeedPIDController, 速度环反馈控制
        #          state["input_lpf"]: 中值滤波去尖刺, window=5
        #          state["diff_filter"]: 差分限幅(max_delta=5.0)防止突变
        #          state["dual_filter"]: 双窗口回归融合(来自 build_wheel_state)
        #          state["output_lpf"]: 低通滤波平滑(来自 build_wheel_state)
        #          state["raw_speed"]: 编码器原始速度(脉冲/周期)
        #          state["filtered_speed"]: 多级滤波后的速度
        #          state["duty"]: 当前电机占空比(-MAX_DUTY ~ +MAX_DUTY)
        self.wheel_states = []
        for name in ("m", "l", "r"):
            gain_tau = self.ident_lookup.get(name, (None, None))
            controller = SpeedPIDController(
                output_limit=MAX_DUTY, plant_gain=gain_tau[0], plant_tau=gain_tau[1]
            )
            state = build_wheel_state(
                name,
                self.encoders[name],
                self.motors[name],
                TICK_MS,
                30,
                8,
                pid_controller=controller,
            )
            state["input_lpf"] = SpikeMedianFilter(window=5)
            state["diff_filter"] = DiffLimitFilter(max_delta=5.0)
            self.wheel_states.append(state)

        # 运行期状态变量
        # @details pit_flag: ticker 中断标志, 主循环检测该标志执行一次控制周期
        #          tick_count: 控制周期计数, 用于性能监控和调试
        #          target_speeds: 目标脉冲速度 {"m", "l", "r"}, 由逆运动学计算
        #          control_state: 底盘控制目标, 存储 vx/vy/omega/x/y/angle
        #          command_lock: 位置锁定标志, True 时位置/角度目标有效
        #          command_mode: 当前锁定诊断状态, 取值 locked/unlocked/none
        #          lock_start_time: 位置锁定开始时间(毫秒)
        #          rear_only_mode: 仅后轮模式标志, True 时只驱动中轮
        #          last_rear_mode: 上一周期后轮模式状态, 用于检测模式变化
        #          rx_buf3: UART3 接收缓冲区, 累积接收数据直到完整短包行
        self.pit_flag = False
        self.tick_count = 0
        self.target_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self.command_lock = False
        self.command_mode = "none"
        self.lock_start_time = 0
        self.rear_only_mode = False
        self.last_rear_mode = False
        self.rx_buf3 = ""

        # 时间与性能监控
        # @details ticker: ticker 对象引用, 用于停止中断
        #          boot_time_ms: 系统启动时间戳(毫秒)
        #          last_time_us: 上一周期时间戳(微秒), 用于计算 dt
        #          last_loop_dt_us: 最后一个周期的执行时间(微秒)
        #          max_loop_dt_us: 最大周期执行时间(微秒), 性能峰值
        #          loop_dt_total_us: 累积所有周期执行时间(微秒), 用于计算平均
        #          loop_overrun_count: 周期超时计数, dt > TICK_MS 时递增
        #          last_exception_text: 最后一次异常的字符串表示
        #          _yaw_rate: 当前角速度(度/秒), 滤波后的陀螺仪输出
        #          _last_gz_raw: 最后陀螺仪原始 Z 轴值(用于诊断)
        #          _boot_step_logged: 启动日志标志, 防止重复记录
        #          _boot_tick_logged: 首次 ticker 事件日志标志
        self.ticker = None
        self.boot_time_ms = self._now_ms()
        self.last_time_us = self._now_us()
        self.last_loop_dt_us = 0
        self.max_loop_dt_us = 0
        self.loop_dt_total_us = 0
        self.loop_overrun_count = 0
        self.last_exception_text = "none"
        self._yaw_rate = 0.0
        self._last_gz_raw = 0.0
        self._boot_step_logged = False
        self._boot_tick_logged = False

        # 位置控制暂存, 用于控制周期内的坐标变换
        # @details 相对位移或角度目标需要在写入后统一进行世界系到车体系的坐标变换
        self._pending_dx = None
        self._pending_dy = None
        self._pending_d_angle = None
        self._pending_lock = None
        self._rear_mode_changed = False

        # 初始化速度环 PID 增益, 每轮独立配置
        self.init_pid()

        startup_log("transport_car", "init complete")

    # Public API (公开接口)
    def mark_tick(self, _tick=None): # noqa: F841
        """
        @brief ticker 中断回调函数, 中断处理中置位控制周期标志

        @details 此函数作为 ticker 中断的回调被调用, 中断中仅置位标志而不执行耗时工作
                主循环在 step() 中检测该标志并执行完整的控制周期, 防止中断嵌套和栈溢出

        @param _tick 中断传参(未使用), 仅保持接口一致性

        @note 中断上下文中应尽量快速完成, 建议 < 100us
        """
        self.pit_flag = True

    def set_ticker(self, ticker_obj):
        """
        @brief 注册 ticker 对象引用, 用于后续停止中断

        @details 保存 ticker 对象, stop() 方法中调用 ticker.stop() 关闭定时中断

        @param ticker_obj ticker 对象, 需实现 stop() 方法
        """
        self.ticker = ticker_obj

    def _now_ms(self):
        """
        @brief 获取当前毫秒级时间戳

        @details 优先使用 MicroPython 的 ticks_ms, 回退到标准 time.time()*1000
                以兼容主机测试环境

        @return 当前时间的毫秒数(整数)
        """
        ticks_ms = getattr(time, "ticks_ms", None)
        if ticks_ms is not None:
            return int(ticks_ms())
        return int(time.time() * 1000)

    def _now_us(self):
        """
        @brief 获取当前微秒级时间戳

        @details 优先使用 MicroPython 的 ticks_us, 回退到标准 time.time()*1000000
                以兼容主机测试环境

        @return 当前时间的微秒数(整数)
        """
        ticks_us = getattr(time, "ticks_us", None)
        if ticks_us is not None:
            return int(ticks_us())
        return int(time.time() * 1000000)

    def _ticks_diff_us(self, current_us, previous_us):
        """
        @brief 计算两个微秒级时间戳的差值, 正确处理时间戳回绕

        @details 优先使用 MicroPython 的 ticks_diff 处理 32 位计时器回绕情况
                回退到直接相减以兼容主机测试环境

        @param current_us 当前时间戳(微秒)
        @param previous_us 之前的时间戳(微秒)

        @return 时间差值(微秒, 正数)
        """
        ticks_diff = getattr(time, "ticks_diff", None)
        if ticks_diff is not None:
            return int(ticks_diff(current_us, previous_us))
        return int(current_us - previous_us)

    def step(self):
        """
        @brief 执行单次主循环迭代

        @details 主循环流程
        1. 首次执行时记录启动日志
        2. 检测 ticker 标志, 执行单次控制周期 (_handle_tick)
        3. 处理 UART 接收的短包
        4. 检测硬件紧急停止按钮 switch2, 触发时安全停止
        5. 执行垃圾回收, 释放内存
        6. 返回继续运行标志

        @return True 表示继续运行主循环
                False 表示检测到致命错误(如急停)应退出主循环

        @note 此函数应在主循环中反复调用, 典型使用
        @code
            while True:
                if not car.step():
                    break
        @endcode
        """
        if not self._boot_step_logged:
            startup_log("transport_car", "step loop active")
            self._boot_step_logged = True

        if self.pit_flag:
            if not self._boot_tick_logged:
                startup_log("transport_car", "first ticker event received")
                self._boot_tick_logged = True
            self._handle_tick()
            self.pit_flag = False

        self._process_uart()

        if self.switch2.value() != self.switch2_init:
            self.stop()
            return False

        gc.collect()
        return True

    def stop(self):
        """
        @brief 安全停止控制循环并关闭所有硬件

        @details 停止流程
        1. 停止 ticker 中断, 防止新的控制周期
        2. 重置所有轮子 PID 控制器的积分状态, 清除累积误差
        3. 将所有电机占空比设置为 0, 停止转动
        4. 向 UART3 发送停止确认消息 "stop\r\n"

        @warning 此函数应在检测到致命错误(如急停)时调用, 确保硬件安全
        """
        if self.ticker:
            self.ticker.stop()
        self.zero_motors()
        self.uart3.write("stop\r\n")

    def _handle_uart_line(self, line, source):
        """
        @brief 处理来自串口的单行正式短包

        @details 处理逻辑
        - 空行忽略
        - 非短包或未消费短包忽略
        - 速度短包写入结构化速度入口

        @param line 输入行字符串, 可能为空或已去除首尾空格
        @param source 串口来源标识(如 "uart3"), 用于调试和日志
        """
        if not line:
            return

        packet = parse_short_packet(line)
        if packet is None:
            return

        if packet.get("type") == "v":
            self.handle_velocity_packet(
                float(packet["vx"]),
                float(packet["vy"]),
                float(packet.get("omega", 0.0)),
                source=source,
                has_omega=bool(packet.get("has_omega")),
            )

    def set_velocity_target(self, vx, vy, omega=0.0, has_omega=True):
        """写入结构化速度控制目标

        @param vx 车体系 x 方向速度
        @param vy 车体系 y 方向速度
        @param omega 车体系角速度
        @param has_omega 本次输入是否显式携带角速度
        """

        self.control_state["vx"] = float(vx)
        self.control_state["vy"] = float(vy)
        self._clear_translation_control_targets()

        if has_omega:
            self.control_state["omega"] = float(omega)
            self._clear_rotation_control_targets()

        self._pending_lock = None
        self._refresh_control_mode()

    def reset_control_state(self):
        """复位底盘控制状态、姿态估计和控制器积分."""

        self.odometry.reset()
        self.heading_est = 0.0
        self.heading_target = 0.0
        self.yaw_pid.reset()
        self.yaw_integral = 0.0
        self.q_est.w, self.q_est.x, self.q_est.y, self.q_est.z = 1.0, 0.0, 0.0, 0.0
        self.last_yaw_rad = 0.0
        self.gyro_lpf.reset(0.0)
        reset_pi_state(self.wheel_states)
        self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self.command_lock = False
        self.command_mode = "none"
        self._pending_lock = None
        self._pending_dx = None
        self._pending_dy = None
        self._pending_d_angle = None

    def zero_motors(self):
        """清零速度环积分和三轮电机输出."""

        reset_pi_state(self.wheel_states)
        for state in self.wheel_states:
            state["motor"].duty(0)
            state["duty"] = 0.0

    def _clear_translation_control_targets(self):
        """清理平移位置目标."""

        self.control_state.pop("x", None)
        self.control_state.pop("y", None)
        self._pending_dx = None
        self._pending_dy = None

    def _clear_rotation_control_targets(self):
        """清理角度位置目标."""

        self.control_state.pop("angle", None)
        self._pending_d_angle = None

    def _refresh_control_mode(self):
        """根据当前结构化控制目标刷新锁定状态."""

        if self._has_active_pose_target():
            self.command_mode = "locked" if self.command_lock else "unlocked"
        else:
            self.command_lock = False
            self.command_mode = "none"

    def handle_velocity_packet(self, vx, vy, omega=0.0, source="protocol", has_omega=True):
        """接收结构化速度短包结果

        @param vx 车体系 x 方向速度
        @param vy 车体系 y 方向速度
        @param omega 车体系角速度
        @param source 输入来源标识
        @param has_omega 本包是否显式携带角速度
        """

        self.set_velocity_target(vx, vy, omega, has_omega=has_omega)

    def _get_active_position_targets(self):
        """
        @brief 获取当前激活的位置目标

        @return 元组 (x, y), 表示目标位置坐标, 可能为 None
        """
        return self.control_state.get("x"), self.control_state.get("y")

    def _has_active_translation_target(self):
        """
        @brief 检查是否存在激活的平移位置目标

        @return True 如果存在 x 或 y 目标, 否则 False
        """
        cmd_x, cmd_y = self._get_active_position_targets()
        return cmd_x is not None or cmd_y is not None

    def _get_active_angle_command(self):
        """
        @brief 获取当前激活的角度目标

        @return 目标角度值, 可能为 None
        """
        return self.control_state.get("angle")

    def _has_active_rotation_target(self):
        """
        @brief 检查是否存在激活的转向位置目标

        @return True 如果存在角度目标, 否则 False
        """
        return self._get_active_angle_command() is not None

    def _has_active_pose_target(self):
        """
        @brief 检查是否存在任一位置式目标

        @return True 如果存在平移或旋转目标, 否则 False
        """
        return self._has_active_translation_target() or self._has_active_rotation_target()

    def _get_active_rear_only_mode(self):
        """
        @brief 获取当前后轮模式状态

        @return True 如果启用仅后轮模式, 否则 False
        """
        return self.rear_only_mode

    def build_health_snapshot(self):
        """
        @brief 构造系统健康状态快照, 用于诊断

        @details 收集当前运行状态
        - alive: 系统在线标志(恒为 1)
        - uptime_ms: 从启动至今的运行时间(毫秒)
        - last_err: 最后一次异常的字符串表示, 用于故障诊断

        @return 包含系统健康字段的字典
        """
        snapshot = {
            "alive": 1,
            "uptime_ms": max(0, self._now_ms() - int(self.boot_time_ms)),
            "last_err": self.last_exception_text,
        }
        snapshot.update(self._build_control_health_fields())
        return snapshot

    def _build_control_health_fields(self):
        """构造底盘控制状态健康字段."""

        return {
            "lock": 1 if self.command_lock else 0,
            "rear": 1 if self._get_active_rear_only_mode() else 0,
            "command_mode": self.command_mode,
        }

    def build_tick_snapshot(self):
        """
        @brief 构造控制周期执行统计快照, 用于性能监控

        @details 统计字段
        - count: 累计执行的控制周期数
        - last_us: 最后一个周期的执行时间(微秒)
        - max_us: 历史最大周期执行时间(微秒)
        - avg_us: 历史平均周期执行时间(微秒)
        - overrun: 超期周期计数(dt > TICK_MS*1000 的次数)

        @return 包含周期统计数据的字典
        """
        avg_us = 0
        if self.tick_count > 0:
            avg_us = int(self.loop_dt_total_us / self.tick_count)
        return {
            "count": int(self.tick_count),
            "last_us": int(self.last_loop_dt_us),
            "max_us": int(self.max_loop_dt_us),
            "avg_us": avg_us,
            "overrun": int(self.loop_overrun_count),
        }

    def build_imu_snapshot(self):
        """
        @brief 构造 IMU 与姿态估计诊断快照

        @details 诊断字段
        - ok: IMU 通信状态(1=正常, 0=异常)
        - yaw_deg: 当前估计的航向角(度)
        - yaw_rate_dps: 滤波后的角速度(度/秒)
        - gz_raw: 最后一次读取的陀螺仪 Z 轴原始值(度/秒)

        @return 包含 IMU 状态的字典
        """
        return {
            "ok": 1 if self.imu_data else 0,
            "yaw_deg": float(self.heading_est),
            "yaw_rate_dps": float(self._yaw_rate),
            "gz_raw": float(self._last_gz_raw),
        }

    def build_encoder_snapshot(self):
        """
        @brief 构造编码器速度观测快照, 用于调试滤波效果

        @details 为三轮提供原始速度和滤波速度对比
        - {m, l, r}_raw: 编码器原始脉冲速度(未滤波)
        - {m, l, r}_filt: 多级滤波后的脉冲速度

        @return 包含各轮速度的字典
        """
        snapshot = {}
        for state in self.wheel_states:
            name = state["name"]
            snapshot["%s_raw" % name] = float(state.get("raw_speed", 0.0))
            snapshot["%s_filt" % name] = float(state.get("filtered_speed", 0.0))
        return snapshot

    def build_motor_snapshot(self):
        """
        @brief 构造电机目标与实际输出快照, 用于验证速度环

        @details 为三轮提供目标速度和实际占空比
        - {m, l, r}_target: 速度环目标速度(脉冲/周期)
        - {m, l, r}_duty: 电机实际输出占空比(-MAX_DUTY ~ +MAX_DUTY)
        - rear: 后轮模式状态(1=仅后轮, 0=全向)

        @return 包含各轮目标与实际的字典
        """
        snapshot = {}
        for state in self.wheel_states:
            name = state["name"]
            snapshot["%s_target" % name] = float(self.target_speeds.get(name, 0.0))
            snapshot["%s_duty" % name] = float(state.get("duty", 0.0))
        snapshot["rear"] = 1 if self._get_active_rear_only_mode() else 0
        return snapshot

    # Internal helpers and control loop (内部助手方法与控制循环)
    def init_pid(self):
        """
        @brief 按 PID_MAP 配置表初始化三轮速度环增益

        @details 为每个轮子从 PID_MAP 读取 (kp, ki, ki2) 三个增益参数
                设置到对应的 SpeedPIDController 中
                默认值 (10.0, 0.5, 0.01) 用于 PID_MAP 中未定义的轮子

        @note ki2 是二阶积分项增益, 用于增强长期稳定性
        """
        for state in self.wheel_states:
            kp_val, ki_val, ki2_val = PID_MAP.get(state["name"], (10.0, 0.5, 0.01))
            state["kp"], state["ki"] = kp_val, ki_val
            state["controller"].set_gains(kp_val, ki_val, ki2_val)

    def _inverse_kinematics(self, vx, vy, omega):
        """
        @brief Y 型三轮全向车的逆运动学, 将车体系速度转换为轮速

        @details 使用解析逆运动学模型
        - vl = (vx/3) + (√3/3)*vy + (omega/3)
        - vr = (vx/3) - (√3/3)*vy + (omega/3)
        - vm = (-2/3)*vx + (omega/3)

        当任意轮速超过上限 TARGET_SPEED_MAX 时, 对所有轮速进行等比例缩放,
        保持方向不变同时满足速度约束

        @param vx 纵向速度(脉冲/周期), 沿车体纵轴正向
        @param vy 横向速度(脉冲/周期), 沿车体横轴正向(左为正)
        @param omega 角速度(脉冲/周期), 逆时针为正

        @return 元组 (vm, vl, vr), 分别对应中轮、左轮、右轮的目标脉冲速度
                均限制在 ±TARGET_SPEED_MAX 范围内

        @note Y 型三轮配置
        - m(中): 车体后方中心
        - l(左): 车体前左方
        - r(右): 车体前右方
        """
        sqrt3 = math.sqrt(3)
        vl = (vx / 3.0) + (sqrt3 / 3.0) * vy + (omega / 3.0)
        vr = (vx / 3.0) - (sqrt3 / 3.0) * vy + (omega / 3.0)
        vm = (-2.0 / 3.0) * vx + (omega / 3.0)

        speeds = [abs(vm), abs(vl), abs(vr)]
        max_speed = max(speeds) if speeds else 0.0
        if max_speed > TARGET_SPEED_MAX and max_speed > 0.0:
            scale = TARGET_SPEED_MAX / max_speed
            vm *= scale
            vl *= scale
            vr *= scale
        return vm, vl, vr

    def _handle_tick(self):
        """
        @brief 执行单次 5ms 控制周期的完整处理流程

        @details 步骤
        1. 更新 LED 状态和周期计数
        2. 计算真实执行周期 dt_us, 检测超期并更新性能监控数据
        3. 读取三轮编码器并通过多级滤波处理得到滤波速度
        4. 更新 IMU 数据、四元数积分、解包航向角、计算滤波角速度
        5. 执行完整控制堆栈: 目标速度生成、逆运动学、速度环 PID、电机驱动

        @note 此函数在中断上下文中调用, 应保持执行时间稳定, 通常 < 4ms
        """
        self.tick_count += 1
        self.led.toggle()

        current_time_us = self._now_us()
        dt_us = self._ticks_diff_us(current_time_us, self.last_time_us)
        self.last_time_us = current_time_us
        self.last_loop_dt_us = int(dt_us)
        self.loop_dt_total_us += int(dt_us)
        if dt_us > self.max_loop_dt_us:
            self.max_loop_dt_us = int(dt_us)
        if dt_us > TICK_MS * 1000:
            self.loop_overrun_count += 1
        dt_s = dt_us / 1000000.0

        self._update_wheel_speeds()
        self._update_attitude(dt_s)
        self._run_control(dt_s)

    def _update_wheel_speeds(self):
        """
        @brief 读取三轮编码器并通过多级滤波器处理得到最终速度

        @details 多级滤波流程
        1. input_lpf(SpikeMedianFilter, window=5): 去尖刺, 中值滤波去除离群值
        2. diff_filter(DiffLimitFilter, max_delta=5.0): 差分限幅, 防止速度突变
        3. dual_filter(双窗回归融合, 来自 build_wheel_state): 低延迟融合平滑
        4. output_lpf(低通滤波器): 最终低通平滑, 得到 filtered_speed

        @note 处理结果存储在 state["filtered_speed"], 供速度环 PID 反馈使用
        """
        for state in self.wheel_states:
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            smooth_raw = state["input_lpf"].update(raw)
            smooth_raw = state["diff_filter"].update(smooth_raw)
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)

    def _update_attitude(self, dt_s):
        """
        @brief 更新 IMU 数据、四元数积分、航向角解包、计算滤波角速度

        @details 处理步骤
        1. 读取 IMU 原始陀螺仪数据, 减去零偏 (imu_offsets) 进行校正
        2. 转换为弧度制(除以 GYRO_SCALE), 并积分四元数以获得精确航向
        3. 从四元数解包偏航角(弧度), 处理 pi 跨越
        4. 将陀螺仪 gz 通过低通滤波转换为角速度(度/秒)
        5. 将三轮滤波速度(脉冲) 转换为地面速度(m/s), 正逆运动学变换
        6. 积分里程计以更新世界系位置 (x, y)

        @param dt_s 时间增量(秒), 用于四元数与里程计积分

        @note 关键参数
        - GYRO_SCALE: 原始陀螺仪读数到度/秒的转换因子
        - GYRO_LPF_ALPHA: 角速度低通滤波系数
        """
        self.imu_data = self.imu.get()
        if self.imu_data:
            gx_raw = float(self.imu_data[3]) - self.imu_offsets[3]
            gy_raw = float(self.imu_data[4]) - self.imu_offsets[4]
            gz_raw = float(self.imu_data[5]) - self.imu_offsets[5]
        else:
            gx_raw = gy_raw = gz_raw = 0.0
        self._last_gz_raw = gz_raw

        rad_scale = (math.pi / 180.0) / GYRO_SCALE
        gx = gx_raw * rad_scale
        gy = gy_raw * rad_scale
        gz = gz_raw * rad_scale

        self.q_est.update(gx, gy, gz, dt_s)

        curr_yaw_rad = self.q_est.to_euler_yaw()
        delta_yaw = curr_yaw_rad - self.last_yaw_rad
        if delta_yaw > math.pi:
            delta_yaw -= 2.0 * math.pi
        elif delta_yaw < -math.pi:
            delta_yaw += 2.0 * math.pi
        self.last_yaw_rad = curr_yaw_rad

        yaw_rate = self.gyro_lpf.update(gz * (180.0 / math.pi))

        vm_pulse = self.wheel_states[0]["filtered_speed"]
        vl_pulse = self.wheel_states[1]["filtered_speed"]
        vr_pulse = self.wheel_states[2]["filtered_speed"]

        vm_mps = self.kinematics.velocity_pulses_to_m_s(vm_pulse, dt_s)
        vl_mps = self.kinematics.velocity_pulses_to_m_s(vl_pulse, dt_s)
        vr_mps = self.kinematics.velocity_pulses_to_m_s(vr_pulse, dt_s)

        vx_rob_mps, vy_rob_mps, _ = self.kinematics.forward_kinematics(
            vm_mps, vl_mps, vr_mps
        )

        self.odometry.update(
            vx_rob_mps, vy_rob_mps, math.radians(self.heading_est), dt_s
        )
        self.heading_est += math.degrees(delta_yaw)

        self._yaw_rate = yaw_rate

    def _run_control(self, dt_s):
        """
        @brief 执行完整的控制堆栈, 从控制目标到电机驱动

        @details 控制流程
        1. _compute_omega_cmd: 根据 angle/omega 控制目标计算目标角速度
        2. _compute_planar_targets: 根据 x/y 或 vx/vy 计算车体系目标速度
        3. _apply_target_speeds: 逆运动学、速度环 PID、电机驱动分配
        4. _check_unlock: 位置锁定模式下检查收敛, 达标时自动解锁

        @param dt_s 时间增量(秒), 用于 PID 积分
        """
        omega_cmd = self._compute_omega_cmd(dt_s)
        target_vx_cmd, target_vy_cmd = self._compute_planar_targets(dt_s)
        self._apply_target_speeds(target_vx_cmd, target_vy_cmd, omega_cmd, dt_s)
        self._check_unlock()

    def _compute_omega_cmd(self, dt_s):
        """
        @brief 根据当前旋转控制目标计算目标角速度, 支持三种模式

        @details 三种模式优先级
        1. 角度模式(cmd_angle != None):
           - 使用位置式 PID 跟踪目标航向角
           - 微分项直接使用滤波角速度, 增强稳定性
           - 输出限幅在 ±AUTO_OMEGA_MAX

        2. 角速度模式(omega != None):
           - 直接跟随控制目标中的 omega 值
           - 当 |omega| < HOLD_SPEED_EPS 时自动切换到保持模式
           - 否则重置 PID, 记录当前航向作为保持目标

        3. 保持模式(都为 None):
           - 维持 heading_target 角度, 通过 PID 自动调整角速度
           - 微分项使用滤波角速度

        @param dt_s 时间增量(秒), 用于 PID 积分

        @return 限幅后的目标角速度(脉冲/周期), 范围 ±AUTO_OMEGA_MAX

        @warning YAW_KD 配置应使用本地微分而不是 PID 的 D 项, 因为已有低通滤波
        """
        cmd_angle = self._get_active_angle_command()
        omega_value = self.control_state.get("omega")

        if cmd_angle is not None:
            self.heading_target = cmd_angle
            omega_pid = self.yaw_pid.update(self.heading_target, self.heading_est, dt_s)
            omega_auto = omega_pid - YAW_KD * self._yaw_rate
            omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)

        elif omega_value is not None:
            omega_cmd = omega_value
            if abs(omega_cmd) < HOLD_SPEED_EPS:
                omega_pid = self.yaw_pid.update(
                    self.heading_target, self.heading_est, dt_s
                )
                omega_auto = omega_pid - YAW_KD * self._yaw_rate
                omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)
            else:
                self.heading_target = self.heading_est
                self.yaw_pid.reset()
                self.yaw_integral = 0.0
        else:
            omega_pid = self.yaw_pid.update(self.heading_target, self.heading_est, dt_s)
            omega_auto = omega_pid - YAW_KD * self._yaw_rate
            omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)

        if hasattr(self.yaw_pid, "integral"):
            self.yaw_integral = self.yaw_pid.integral

        return omega_cmd

    def _compute_planar_targets(self, dt_s):
        """
        @brief 计算车体系平面运动目标速度, 支持位置锁定和速度两种模式

        @details 两种模式
        1. 位置锁定模式(cmd_x 或 cmd_y 有效):
           - 在世界系中计算位置误差 (err_x, err_y) = (target - odometry)
           - 使用 POS_KP 进行 P 控制生成世界系目标速度 (v_world_x, v_world_y)
           - 限幅最大速度为 POS_MAX_SPEED, 防止快速运动时过冲
           - 通过旋转矩阵变换到车体系(相对当前航向)
           - 最后转换为脉冲/周期单位并扩展 3 倍(适配逆运动学)

        2. 速度模式(cmd_x/cmd_y 都为 None):
           - 直接使用 vx/vy 控制目标(已为脉冲/周期单位)

        @param dt_s 时间增量(秒), 此处未直接使用, 保留用于扩展

        @return 元组 (target_vx_cmd, target_vy_cmd), 单位为脉冲/周期
                已经过逆运动学预处理(乘以 3.0)

        @warning 位置模式中的旋转矩阵实现了世界系→车体系的坐标变换
                注意当前航向角 heading_est 是度数, 需转为弧度
        """
        target_vx_cmd = 0.0
        target_vy_cmd = 0.0

        cmd_x, cmd_y = self._get_active_position_targets()

        if cmd_x is not None or cmd_y is not None:
            t_x = cmd_x if cmd_x is not None else 0.0
            t_y = cmd_y if cmd_y is not None else 0.0

            err_x = t_x - self.odometry.x
            err_y = t_y - self.odometry.y

            v_world_x = err_x * POS_KP
            v_world_y = err_y * POS_KP

            v_speed = math.sqrt(v_world_x * v_world_x + v_world_y * v_world_y)
            if v_speed > POS_MAX_SPEED:
                scale = POS_MAX_SPEED / v_speed
                v_world_x *= scale
                v_world_y *= scale

            t_rad = math.radians(self.heading_est)
            cos_t = math.cos(t_rad)
            sin_t = math.sin(t_rad)

            vx_rob_ctrl = v_world_x * cos_t + v_world_y * sin_t
            vy_rob_ctrl = -v_world_x * sin_t + v_world_y * cos_t

            vx_pulses = self.kinematics.velocity_m_s_to_pulses(vx_rob_ctrl, dt_s)
            vy_pulses = self.kinematics.velocity_m_s_to_pulses(vy_rob_ctrl, dt_s)

            target_vx_cmd = vx_pulses * 3.0
            target_vy_cmd = vy_pulses * 3.0

        else:
            target_vx_cmd = float(self.control_state.get("vx", 0.0))
            target_vy_cmd = float(self.control_state.get("vy", 0.0))

        return target_vx_cmd, target_vy_cmd

    def _apply_target_speeds(self, target_vx_cmd, target_vy_cmd, omega_cmd, dt_s):
        """
        @brief 执行逆运动学、限幅、速度环 PID 控制, 分配占空比到三轮

        @details 处理步骤
        1. 逆运动学: 将车体系控制目标 (vx, vy, omega) 转换为三轮脉冲速度目标 (vm, vl, vr)
        2. 限幅: 所有轮速限制在 ±TARGET_SPEED_MAX 范围内
        3. 后轮模式处理: 若启用 rear_only_mode, 中轮 1/3 速度、左右轮停止
        4. 对每个活跃轮子运行速度环 PID:
           - 比较目标速度与滤波反馈速度
           - 输出电机占空比(限幅 ±MAX_DUTY)
           - 直接驱动电机
        5. 非活跃轮子重置 PID 并停止

        @param target_vx_cmd 目标纵向速度(脉冲/周期)
        @param target_vy_cmd 目标横向速度(脉冲/周期)
        @param omega_cmd 目标角速度(脉冲/周期)
        @param dt_s 时间增量(秒), 用于 PID 积分

        @note ACTIVE_WHEELS 定义了活跃的轮子集合, 其他轮子维持零速度
        """
        vm, vl, vr = self._inverse_kinematics(
            target_vx_cmd,
            target_vy_cmd,
            float(omega_cmd),
        )

        if self._get_active_rear_only_mode():
            self.target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX) / 3
            self.target_speeds["l"] = 0.0
            self.target_speeds["r"] = 0.0
        else:
            self.target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
            self.target_speeds["l"] = clamp(vl, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
            self.target_speeds["r"] = clamp(vr, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)

        for state in self.wheel_states:
            if state["name"] in ACTIVE_WHEELS:
                tgt = clamp(
                    self.target_speeds.get(state["name"], 0.0),
                    -TARGET_SPEED_MAX,
                    TARGET_SPEED_MAX,
                )
                duty_cmd = state["controller"].update(
                    tgt, state["filtered_speed"], dt_s
                )
                state["duty"] = duty_cmd
                state["motor"].duty(int(duty_cmd))
            else:
                state["controller"].reset()
                state["duty"] = 0.0
                state["motor"].duty(0)

    def _check_unlock(self):
        """
        @brief 在位置锁定模式下检查目标收敛条件, 达标时自动解锁

        @details 解锁判据
        1. 角度检查(如果有旋转目标):
           - 当前航向与目标航向差 < ANGLE_TOLERANCE(度)
        2. 位置检查(如果有平移目标):
           - 当前位置与目标位置欧氏距离 < POS_TOLERANCE(米)

        解锁后:
        - 若启用后轮模式(rear_only_mode=True), 则:
          a. 关闭后轮模式, 回归全向运动
          b. 清空速度控制目标
          c. 重置所有 PID 积分
          d. 停止所有电机
        - 其他模式: 仅清除位置锁定状态

        @warning 此函数应在每个控制周期末尾调用, 以实时响应收敛事件
        """
        if not self.command_lock:
            return

        angle_ok = True
        if self._has_active_rotation_target():
            err_angle = abs(self.heading_target - self.heading_est)
            if err_angle > ANGLE_TOLERANCE:
                angle_ok = False

        pos_ok = True
        if self._has_active_translation_target():
            tx_chk = self.control_state.get("x")
            ty_chk = self.control_state.get("y")
            tx_val = tx_chk if tx_chk is not None else 0.0
            ty_val = ty_chk if ty_chk is not None else 0.0

            ex_val = tx_val - self.odometry.x
            ey_val = ty_val - self.odometry.y
            dist_err = math.sqrt(ex_val * ex_val + ey_val * ey_val)

            if dist_err > POS_TOLERANCE:
                pos_ok = False

        if angle_ok and pos_ok:
            self.command_lock = False
            self.command_mode = "none"
            if self.rear_only_mode:
                self.rear_only_mode = False
                self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
                reset_pi_state(self.wheel_states)
                self.yaw_pid.reset()
                self.yaw_integral = 0.0
                self.heading_target = self.heading_est
                for state in self.wheel_states:
                    state["motor"].duty(0)
                    state["duty"] = 0.0

    def _process_uart(self):
        """
        @brief 轮询 UART3 接收缓冲区, 处理正式短包输入

        @details 处理流程
        1. 检查 UART3 缓冲区是否有待接收字节
        2. 解码接收数据追加到接收缓冲 rx_buf3
        3. 按行分割(以 \n 为界), 去除 \r 和首尾空格
        4. 对每行调用 _handle_uart_line 进行正式短包分发
        5. 异常时向串口回写错误信息

        @warning 此函数在主循环中非中断上下文调用, 可安全执行耗时操作
        """
        buf_len = self.uart3.any()
        if buf_len:
            try:
                self.rx_buf3 += self.uart3.read(buf_len).decode()
                while True:
                    idx = self.rx_buf3.find("\n")
                    if idx == -1:
                        break
                    line = self.rx_buf3[: idx].rstrip("\r").strip()
                    self.rx_buf3 = self.rx_buf3[idx + 1 : ]
                    self._handle_uart_line(line, source="uart3")
            except Exception as exc:
                self.last_exception_text = str(exc)
                self.uart3.write("ERR %s\r\n" % exc)
