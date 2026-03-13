"""搬运车控制单例封装,拆出原 remote_control.py 的全部逻辑."""

import gc
import math
import time

from machine import Pin
from control.wheel import build_wheel_state
from control.pid_controller import SpeedPIDController, PositionalPIDController
from control.pid_math import clamp, reset_pi_state
from control.kinematics import OmniKinematics, Odometry
from control.chassis_state import ChassisState
from control.attitude_estimator import AttitudeEstimator
from control.wheel_speed_controller import WheelSpeedController
from control.motion_planner import MotionPlanner
from control.chassis_controller import ChassisController
from filters.lowpass_filter import LowPassFilter
from filters.spike_filter import SpikeMedianFilter
from filters.diff_limit_filter import DiffLimitFilter
from utils.quaternion import Quaternion
from config.params import (
    TICK_MS,
    MAX_DUTY,
    TARGET_SPEED_MAX,
    POS_MAX_SPEED,
    POS_KP,
    POS_TOLERANCE,
    ANGLE_TOLERANCE,
    ACTIVE_WHEELS,
    GYRO_LPF_ALPHA,
    GYRO_SCALE,
    YAW_KP,
    YAW_KI,
    YAW_KD,
    YAW_I_MAX,
    AUTO_OMEGA_MAX,
    HOLD_SPEED_EPS,
    IDENT_RESULTS_FILE,
    GYRO_OFFSET_FILE,
    PID_MAP,
    VISION_OBSERVATION_TIMEOUT_MS,
    VISION_TARGET_BOTTOM_PX,
    VISION_TARGET_CENTER_X_PX,
    VISION_ANGLE_KP,
    VISION_DIST_KP,
    VISION_DX_KP,
    VISION_PUSH_DX_KP,
    VISION_PUSH_DY_M,
    VISION_PUSH_DISTANCE_M,
    VISION_PUSH_ANGLE_DEG,
    VISION_ANGLE_DEADZONE_PX,
    VISION_ANGLE_REENTRY_PX,
    VISION_DIST_DEADZONE_PX,
    VISION_DX_DEADZONE_PX,
    VISION_HEADING_TOLERANCE_DEG,
    VISION_STABLE_FRAMES,
    VISION_MAX_DX_M,
    VISION_MAX_DY_M,
    VISION_MAX_D_ANGLE_DEG,
    VISION_DONE_HOLD_MS,
)
from hardware.uart_bus import create_uart3, create_uart6
from hardware.motors import create_motors
from hardware.encoders import create_encoders
from hardware.imu import create_imu
from storage.param_manager import load_ident_lookup, load_gyro_offsets
from services.commanding.context import TransportCommandContext
from services.commanding.session import CommandSession
from services.commanding.router import router as _cmd_router
from services.runtime.diagnostics_facade import DiagnosticsFacade
from services.runtime.uart_ingress import UartIngressService
from diagnostics.manager import build_uart3_logger_manager
from vision.coordinator import VisionCoordinator
from vision.debug import build_logger_debug_sink
from vision.protocol import VisionProtocol
from vision.state_registry import vision_state_registry
from vision.state_machine import VisionStateConfig, VisionStateMachine
from vision.transforms import normalize_angle
import services.commanding.handlers as _commanding_handlers


_commanding_handlers.load_all_handlers()


class _NullImu:
    """Stage 2 安全模式下使用的空 IMU."""

    def get(self):
        """返回全零六轴数据."""
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class _NullEncoder:
    """Stage 2 安全模式下使用的空编码器."""

    def get(self):
        """返回零脉冲."""
        return 0.0


class _NullMotor:
    """Stage 2 安全模式下使用的空电机."""

    def __init__(self):
        """初始化空电机占空比记录."""
        self.last_duty = 0

    def duty(self, value):
        """记录占空比但不触发真实输出."""
        self.last_duty = int(value)


def _create_null_encoders():
    """构造三轮空编码器集合."""
    return {"m": _NullEncoder(), "l": _NullEncoder(), "r": _NullEncoder()}


def _create_null_motors():
    """构造三轮空电机集合."""
    return {"m": _NullMotor(), "l": _NullMotor(), "r": _NullMotor()}


class TransportCar:
    """搬运车核心控制单例,集硬件、运动学、PID 控制、命令路由于一体.

    主要责任:
    - 硬件初始化与资源管理(电机、编码器、IMU、串口)
    - 周期性控制循环(5ms 周期)
    - 速度闭环与运动学变换
    - 位置锁定与偏航角控制
    - 串口命令解析和执行

    使用模式::

        car = TransportCar()
        car.set_ticker(ticker_obj)  # 注册 5ms 周期中断
        while True:
            if not car.step():
                break  # 检测到急停或其他致命错误
    """

    def __init__(self, diagnostic_mode=False):
        """初始化搬运车所有组件.

        完成硬件初始化、滤波器和状态变量的构造,保持所有参数与旧版一致.
        包括电机、编码器、IMU、运动学、PID 控制器、串口等.
        """
        self.diagnostic_mode = bool(diagnostic_mode)

        # 板载 LED 与停止开关
        self.led = Pin("C4", Pin.OUT, value=True)
        self.switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
        self.switch2_init = self.switch2.value()

        # 串口(保持原波特率与编号)
        self.uart3 = create_uart3()
        self.uart6 = create_uart6()
        self.logger_manager = build_uart3_logger_manager(self.uart3)
        self.log_system = self.logger_manager.get_logger("system.boot")
        self.log_command = self.logger_manager.get_logger("services.command")
        self.log_vision = self.logger_manager.get_logger("vision.state")
        self.log_health = self.logger_manager.get_logger("system.health")
        self.log_system.info("System Starting...")

        # IMU 初始化
        if self.diagnostic_mode:
            self.log_system.info("Diagnostic mode: skip IMU init.")
            self.imu = _NullImu()
        else:
            self.log_system.info("Initializing IMU...")
            self.imu = create_imu()
        imu_data = self.imu.get()

        # 滤波与姿态估计状态
        gyro_lpf = LowPassFilter(alpha=GYRO_LPF_ALPHA, initial=0.0)
        heading_est = 0.0
        q_est = Quaternion()
        last_yaw_rad = 0.0

        # 偏航角姿态 PID(位置式,输出角速度)
        yaw_pid = PositionalPIDController(
            output_limit=AUTO_OMEGA_MAX, integral_limit=YAW_I_MAX
        )
        yaw_pid.set_gains(YAW_KP, YAW_KI, 0.0)
        yaw_integral = 0.0  # 保留字段便于调试显示

        # 运动学与里程计
        kinematics = OmniKinematics()
        odometry = Odometry()

        # Heading targets
        heading_target = 0.0

        # Motors and encoders
        if self.diagnostic_mode:
            self.log_system.info("Diagnostic mode: skip motor/encoder init.")
            self.motors = _create_null_motors()
            self.encoders = _create_null_encoders()
        else:
            self.motors = create_motors()
            self.encoders = create_encoders()

        # 辨识参数加载
        self.log_system.info("Loading identify parameters...")
        self.ident_lookup = load_ident_lookup(IDENT_RESULTS_FILE)

        # IMU 零偏加载
        imu_offsets = load_gyro_offsets(
            GYRO_OFFSET_FILE, logger=lambda msg: self.log_system.info(msg)
        )

        # 轮组状态构造:滤波、PID、编码器/电机封装
        wheel_states = []
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
            wheel_states.append(state)

        # 运行期状态
        self.pit_flag = False
        self.tick_count = 0
        target_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self._command_session = CommandSession()
        self.chassis_state = ChassisState(
            wheel_states=wheel_states,
            target_speeds=target_speeds,
            yaw_pid=yaw_pid,
            heading_est=heading_est,
            heading_target=heading_target,
            yaw_integral=yaw_integral,
            odometry=odometry,
            kinematics=kinematics,
            gyro_lpf=gyro_lpf,
            q_est=q_est,
            last_yaw_rad=last_yaw_rad,
            imu=self.imu,
            imu_data=imu_data,
            imu_offsets=imu_offsets,
            yaw_rate=0.0,
            last_gz_raw=0.0,
        )
        self.chassis_controller = ChassisController(
            state=self.chassis_state,
            wheel_speed_controller=WheelSpeedController(kinematics),
            attitude_estimator=AttitudeEstimator(),
            motion_planner=MotionPlanner(kinematics),
            uart_writer=self.uart3,
        )

        self.ticker = None
        self.boot_time_ms = self._now_ms()
        self.last_time_us = self._now_us()
        self.last_loop_dt_us = 0
        self.max_loop_dt_us = 0
        self.loop_dt_total_us = 0
        self.loop_overrun_count = 0
        self.last_exception_text = "none"
        # 初始化三轮 PID 增益(与旧版一致)
        self.init_pid()

        # 命令路由器:使用单例路由器(命令模块已通过 @router 装饰器完成注册)
        self._router = _cmd_router

        # 视觉协议与状态机
        vision_protocol = VisionProtocol(timeout_ms=VISION_OBSERVATION_TIMEOUT_MS)
        vision_state_machine = VisionStateMachine(
            self._build_vision_state_config(),
            debug_sink=self._emit_vision_debug,
        )
        self.vision_coordinator = VisionCoordinator(
            protocol=vision_protocol,
            state_machine=vision_state_machine,
        )
        self.uart_ingress = UartIngressService(
            router=self._router,
            vision_coordinator=self.vision_coordinator,
            build_context=self._build_handler_context,
            apply_command=self.apply_command,
            command_log=self._log_uart_command,
            emit_error=self._emit_error_log,
            now_ms=self._now_ms,
        )

    # Public API -----------------------------------------------------
    def mark_tick(self, _tick=None):  # noqa: F841
        """中断处理函数:被 ticker 回调时置位标志.

        ticker 中断仅设置标志,耗时工作放在主循环执行.

        参数:
            _tick: 中断参数(未使用,仅保持接口一致).
        """
        # ticker 中断仅设置标志,耗时工作放在主循环
        self.pit_flag = True

    def set_ticker(self, ticker_obj):
        """记录 ticker 实例,便于 stop 时关闭.

        参数:
            ticker_obj: ticker 对象,支持 .stop() 方法.
        """
        self.ticker = ticker_obj

    def _build_vision_state_config(self):
        """构造视觉状态机参数对象."""
        return VisionStateConfig(
            target_center_x_px=VISION_TARGET_CENTER_X_PX,
            target_bottom_px=VISION_TARGET_BOTTOM_PX,
            angle_kp=VISION_ANGLE_KP,
            dist_kp=VISION_DIST_KP,
            dx_kp=VISION_DX_KP,
            push_dx_kp=VISION_PUSH_DX_KP,
            push_dy_m=VISION_PUSH_DY_M,
            push_distance_m=VISION_PUSH_DISTANCE_M,
            push_angle_deg=VISION_PUSH_ANGLE_DEG,
            angle_deadzone_px=VISION_ANGLE_DEADZONE_PX,
            angle_reentry_px=VISION_ANGLE_REENTRY_PX,
            dist_deadzone_px=VISION_DIST_DEADZONE_PX,
            dx_deadzone_px=VISION_DX_DEADZONE_PX,
            heading_tolerance_deg=VISION_HEADING_TOLERANCE_DEG,
            stable_frames=VISION_STABLE_FRAMES,
            max_dx_m=VISION_MAX_DX_M,
            max_dy_m=VISION_MAX_DY_M,
            max_d_angle_deg=VISION_MAX_D_ANGLE_DEG,
            done_hold_ms=VISION_DONE_HOLD_MS,
        )

    def _emit_vision_debug(self, event) -> None:
        """输出单条视觉状态迁移调试事件."""
        build_logger_debug_sink(self.log_vision)(event)

    def _emit_error_log(self, message: str) -> None:
        """记录结构化错误日志并更新最近异常文本."""
        self.last_exception_text = str(message)
        self.log_health.error(self.last_exception_text)

    def _log_uart_command(self, line: str) -> None:
        """记录来自 UART3 的原始命令文本."""
        self.log_command.info("RCV: %s" % line)

    def _now_ms(self):
        """返回当前毫秒时间戳,兼容主机测试环境."""
        ticks_ms = getattr(time, "ticks_ms", None)
        if ticks_ms is not None:
            return int(ticks_ms())
        return int(time.time() * 1000)

    def now_ms(self):
        """返回公开毫秒时间戳接口."""
        return self._now_ms()

    def _now_us(self):
        """返回当前微秒时间戳,兼容主机测试环境."""
        ticks_us = getattr(time, "ticks_us", None)
        if ticks_us is not None:
            return int(ticks_us())
        return int(time.time() * 1000000)

    def _ticks_diff_us(self, current_us, previous_us):
        """计算两个微秒时间戳差值,兼容主机测试环境."""
        ticks_diff = getattr(time, "ticks_diff", None)
        if ticks_diff is not None:
            return int(ticks_diff(current_us, previous_us))
        return int(current_us - previous_us)

    def step(self):
        """单次主循环:控制、命令处理、急停检测.

        返回:
            True 表示继续运行;False 表示检测到致命错误(如急停开关).
        """
        if self.pit_flag:
            # 仅当标志置位时才执行一次完整控制周期
            self._handle_tick()
            self.pit_flag = False

        # 解析串口指令并更新 last_cmd / 查询回应
        self._process_uart()

        # 硬件急停开关检测
        if self.switch2.value() != self.switch2_init:
            self.stop()
            return False

        gc.collect()
        return True

    def stop(self):
        """停止控制循环、清零积分、断开电机.

        副作用:
            停止 ticker、重置所有 PID 控制器、设置电机占空比为 0、
            向 UART3 输出 "stop" 信息.
        """
        if self.ticker:
            self.ticker.stop()
        chassis_state = self.chassis_state
        wheel_states = []
        if chassis_state is not None:
            wheel_states = chassis_state.wheel_states or []
        reset_pi_state(wheel_states)
        for state in wheel_states:
            state["motor"].duty(0)
        self.uart3.write("stop\r\n")

    @property
    def command_session(self):
        """返回命令会话, 缺失时按需补建."""
        session = getattr(self, "_command_session", None)
        if session is None:
            session = CommandSession()
            self._command_session = session
        return session

    @property
    def chassis_state(self):
        """返回底盘状态 owner."""
        return getattr(self, "_chassis_state", None)

    @chassis_state.setter
    def chassis_state(self, value):
        self._chassis_state = value
        controller = getattr(self, "chassis_controller", None)
        if controller is not None and hasattr(controller, "state"):
            controller.state = value

    def _build_handler_context(self, source="uart6"):
        """构造一次路由调用所需的显式 handler 上下文."""
        reply_uart = getattr(self, source, None)
        if reply_uart is None:
            reply_uart = self.uart6
        return TransportCommandContext(self, reply_uart=reply_uart, source=source)

    def _handle_uart_line(self, line, source):
        """按来源处理单行串口输入."""
        self._ensure_uart_ingress().handle_line(line, source)

    def handle_uart_line(self, line, source="uart6"):
        """公开单行串口入口, 供诊断与外部工具复用."""
        self._handle_uart_line(line, source)

    def _get_vision_resolved_target(self):
        """返回视觉协调器持有的最新解析目标."""
        coordinator = getattr(self, "vision_coordinator", None)
        if coordinator is None:
            return None
        return getattr(coordinator, "resolved_target", None)

    def get_diagnostics_facade(self):
        """返回当前运行时诊断 facade."""
        facade = getattr(self, "_diagnostics_facade", None)
        if facade is None:
            facade = DiagnosticsFacade(self)
            self._diagnostics_facade = facade
        return facade

    def _refresh_vision_target(self, now_ms=None):
        """推进视觉状态机并刷新当前视觉目标."""
        if now_ms is None:
            now_ms = self._now_ms()

        coordinator = self._ensure_vision_coordinator()
        session = self.command_session
        chassis_state = self.chassis_state
        if chassis_state is None:
            return
        odometry = chassis_state.odometry
        heading_est = float(chassis_state.heading_est or 0.0)
        refresh_result = coordinator.refresh(
            now_ms=now_ms,
            heading_deg=heading_est,
            odom_x=float(odometry.x if odometry is not None else 0.0),
            odom_y=float(odometry.y if odometry is not None else 0.0),
            command_lock=session.command_lock,
        )
        released_heading_lock = bool(refresh_result.released_heading_lock)
        if released_heading_lock:
            # 视觉本拍不再输出角度目标时,立即释放上一拍残留的姿态锁定
            chassis_state.heading_target = heading_est
            yaw_pid = chassis_state.yaw_pid
            if yaw_pid is not None:
                yaw_pid.reset()
            chassis_state.yaw_integral = 0.0

    def _get_active_position_targets(self):
        """返回当前激活控制源的位置目标."""
        resolved_target = self._get_vision_resolved_target()
        if resolved_target is not None:
            return resolved_target.x, resolved_target.y
        last_cmd = self.command_session.last_cmd
        return last_cmd.get("x"), last_cmd.get("y")

    def _get_active_angle_command(self):
        """返回当前激活控制源的角度目标."""
        resolved_target = self._get_vision_resolved_target()
        if resolved_target is not None:
            return resolved_target.angle_deg
        return self.command_session.last_cmd.get("angle")

    def _compute_angle_error_deg(
        self, target_angle: float, current_angle: float
    ) -> float:
        """计算最短路径角差, 统一规范角与连续角语义."""
        return normalize_angle(float(target_angle) - float(current_angle))

    def _resolve_continuous_heading_target(
        self, target_angle: float, current_angle: float
    ) -> float:
        """将目标角映射到当前连续航向附近, 避免跨圈追踪."""
        return float(current_angle) + self._compute_angle_error_deg(
            target_angle, current_angle
        )

    def _get_active_rear_only_mode(self):
        """返回当前激活控制源的后轮模式."""
        resolved_target = self._get_vision_resolved_target()
        if resolved_target is not None:
            return resolved_target.rear_only_mode
        return self.command_session.rear_only_mode

    def _get_vision_state_name(self):
        """返回当前视觉状态机状态名."""
        coordinator = getattr(self, "vision_coordinator", None)
        if coordinator is None:
            return "UNKNOWN"
        if hasattr(coordinator, "get_state_name"):
            return coordinator.get_state_name()
        state_machine = getattr(coordinator, "state_machine", None)
        state = getattr(state_machine, "state", None)
        if state is None:
            return "UNKNOWN"
        return vision_state_registry.get_state_name(int(state))

    def get_query_uart(self):
        """返回当前查询响应应写入的串口."""
        return self.uart6

    # Internal helpers ----------------------------------------------
    def init_pid(self):
        """按 PID_MAP 配置表初始化三轮速度环增益."""
        chassis_state = self.chassis_state
        if chassis_state is None:
            return
        wheel_states = chassis_state.wheel_states or []
        for state in wheel_states:
            kp_val, ki_val, ki2_val = PID_MAP.get(state["name"], (10.0, 0.5, 0.01))
            state["kp"], state["ki"] = kp_val, ki_val
            state["controller"].set_gains(kp_val, ki_val, ki2_val)

    def _inverse_kinematics(self, vx, vy, omega):
        """Y 型三轮逆运动学:输入车体系速度/角速度,输出三轮目标脉冲速度.

        参数:
            vx: 纵向速度(脉冲/周期).
            vy: 横向速度(脉冲/周期).
            omega: 角速度(脉冲/周期).

        返回:
            元组 (vm, vl, vr),限制在 ±TARGET_SPEED_MAX 范围内.
        """
        return self._ensure_chassis_controller().inverse_kinematics(vx, vy, omega)

    def inverse_kinematics(self, vx, vy, omega):
        """返回公开逆运动学接口."""
        return self._inverse_kinematics(vx, vy, omega)

    def _handle_tick(self):
        """执行单次 5ms 控制周期.

        包括读取编码器、更新滤波器、IMU 更新、PID 控制、运动学变换.
        """
        self._refresh_vision_target()

        # 记录周期计数并闪烁 LED 作为心跳
        self.tick_count += 1
        self.led.toggle()

        # 计算真实 dt(微秒差),即便打印阻塞也能保持积分正确
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

        # 依次执行:轮速滤波 -> 姿态更新 -> 控制计算
        controller = getattr(self, "chassis_controller", None)
        session = self.command_session
        state = self.chassis_state
        if controller is None:
            self._update_wheel_speeds()
            self._update_attitude(dt_s)
            self._run_control(dt_s)
            return

        active_target_x, active_target_y = self._get_active_position_targets()
        cmd_omega = (
            None
            if self._get_vision_resolved_target() is not None
            else session.last_cmd.get("omega")
        )
        if not hasattr(controller, "state"):
            controller.tick(
                dt_s=dt_s,
                active_target_x=active_target_x,
                active_target_y=active_target_y,
                active_angle=self._get_active_angle_command(),
                cmd_omega=cmd_omega,
                active_rear_only_mode=self._get_active_rear_only_mode(),
                last_cmd=session.last_cmd,
                command_lock=session.command_lock,
                rear_only_mode=session.rear_only_mode,
            )
            return

        tick_result = controller.tick(
            dt_s=dt_s,
            active_target_x=active_target_x,
            active_target_y=active_target_y,
            active_angle=self._get_active_angle_command(),
            cmd_omega=cmd_omega,
            active_rear_only_mode=self._get_active_rear_only_mode(),
            last_cmd=session.last_cmd,
            command_lock=session.command_lock,
            rear_only_mode=session.rear_only_mode,
        )
        if tick_result is not None:
            session.command_lock, session.rear_only_mode, session.last_cmd = tick_result

    def _build_chassis_controller(self):
        """按当前对象字段懒构造底盘控制器."""
        state = getattr(self, "_chassis_state", None)
        if state is None:
            kinematics = OmniKinematics()
            state = ChassisState(
                wheel_states=[],
                target_speeds={"m": 0.0, "l": 0.0, "r": 0.0},
                odometry=Odometry(),
                kinematics=kinematics,
                imu=_NullImu(),
                imu_offsets=[0.0] * 6,
            )
        else:
            kinematics = state.kinematics
        return ChassisController(
            state=state,
            wheel_speed_controller=WheelSpeedController(kinematics),
            attitude_estimator=AttitudeEstimator(),
            motion_planner=MotionPlanner(kinematics),
            uart_writer=getattr(self, "uart3", None),
        )

    def _ensure_chassis_controller(self):
        """返回底盘控制器, 缺失时懒创建."""
        controller = getattr(self, "chassis_controller", None)
        if controller is None:
            controller = self._build_chassis_controller()
            self.chassis_controller = controller
            self.chassis_state = controller.state
        return controller

    def _update_wheel_speeds(self):
        """读取编码器脉冲并通过多级滤波器处理.

        依次执行:中值滤波(去尖刺)→ 差分限幅(限突变)→ 双窗回归(融合)→ 低通(平滑).
        结果存储在 state["filtered_speed"].
        """
        self._ensure_chassis_controller().update_wheel_speeds()

    def _update_attitude(self, dt_s):
        """更新 IMU 数据、四元数积分、解包偏航角、计算滤波角速度.

        参数:
            dt_s: 时间增量(秒).

        副作用:
            修改 self.q_est、self.last_yaw_rad、self.heading_est 等姿态状态.
        """
        self._ensure_chassis_controller().update_attitude(dt_s)

    def _run_control(self, dt_s):
        """执行完整的控制堆栈:姿态环 + 平面运动控制 + 速度环.

        依次:角度/速度指令 → 目标角速度 → 车体系速度命令 → 逆运动学 → 电机占空比.

        参数:
            dt_s: 时间增量(秒).

        副作用:
            更新所有轮子的 state["duty"],并驱动电机.
        """
        # 1) 角度/角速度指令 -> 角速度命令
        omega_cmd = self._compute_omega_cmd(dt_s)

        # 2) 位置/速度指令 -> 车体系 vx, vy 命令(脉冲)
        target_vx_cmd, target_vy_cmd = self._compute_planar_targets(dt_s)

        # 3) 逆运动学 + 速度环闭环,占空比分配
        self._apply_target_speeds(target_vx_cmd, target_vy_cmd, omega_cmd, dt_s)

        # 4) 锁定判定与自动解锁
        self._check_unlock()

    def _compute_omega_cmd(self, dt_s):
        """根据 angle/omega 指令计算目标角速度.

        支持三种模式:
        1. 角度模式(angle 有效):PID 跟踪目标角度.
        2. 角速度模式(omega 有效):直接跟随,极小时自动保持角度.
        3. 保持模式(两者都无):维持当前角度.

        参数:
            dt_s: 时间增量(秒).

        返回:
            目标角速度(限幅在 ±AUTO_OMEGA_MAX 范围内).
        """
        cmd_omega = (
            None
            if self._get_vision_resolved_target() is not None
            else self.command_session.last_cmd.get("omega")
        )
        omega_cmd = self._ensure_chassis_controller().compute_omega_cmd(
            dt_s, self._get_active_angle_command(), cmd_omega
        )
        return omega_cmd

    def _compute_planar_targets(self, dt_s):
        """计算车体系目标速度,支持位置锁定和速度两种模式.

        位置模式:世界系 P 控制 (x, y) → 车体系速度命令.
        速度模式:直接使用 vx, vy 指令.

        参数:
            dt_s: 时间增量(秒).

        返回:
            元组 (target_vx_脉冲, target_vy_脉冲).
        """
        active_target_x, active_target_y = self._get_active_position_targets()
        target_vx_cmd, target_vy_cmd = (
            self._ensure_chassis_controller().compute_planar_targets(
                dt_s, active_target_x, active_target_y, self.command_session.last_cmd
            )
        )
        return target_vx_cmd, target_vy_cmd

    def _apply_target_speeds(self, target_vx_cmd, target_vy_cmd, omega_cmd, dt_s):
        """逆运动学、限幅、速度环 PID,占空比分配到三轮.

        参数:
            target_vx_cmd: 目标纵向速度(脉冲/周期).
            target_vy_cmd: 目标横向速度(脉冲/周期).
            omega_cmd: 目标角速度(脉冲/周期).
            dt_s: 时间增量(秒).

        副作用:
            更新每个轮子的 state["duty"] 并驱动电机.
        """
        self._ensure_chassis_controller().apply_target_speeds(
            target_vx_cmd,
            target_vy_cmd,
            omega_cmd,
            dt_s,
            self._get_active_rear_only_mode(),
        )

    def _check_unlock(self):
        """在锁定模式下检查角度/位置误差,达标时解锁.

        当角度误差 < ANGLE_TOLERANCE 且位置误差 < POS_TOLERANCE 时,
        退出锁定模式.若启用后轮模式,解锁后自动回归全向并停车.

        副作用:
            修改 self.command_lock、self.rear_only_mode、self.target_speeds.
        """
        session = self.command_session
        session.command_lock, session.rear_only_mode, session.last_cmd = (
            self._ensure_chassis_controller().check_unlock(
                session.last_cmd,
                session.command_lock,
                session.rear_only_mode,
            )
        )

    def _process_uart(self):
        """轮询两个串口:处理查询和运动指令.

        UART3:收集调试命令(来自 RTT 或其他监控工具).
        UART6:收集远程操控命令.
        两个串口均支持查询指令(前缀 "?")和控制指令(key=val 格式).

        异常时向串口回写错误信息.
        """
        self._poll_uart_source(self.uart3, "uart3")
        self._poll_uart_source(self.uart6, "uart6")

    def _poll_uart_source(self, uart, source):
        """轮询单个串口,并按行转交给统一处理入口."""
        self._ensure_uart_ingress().poll_source(uart, source)

    def _ensure_vision_coordinator(self):
        """返回视觉协调器, 缺失时按当前依赖懒构造."""
        coordinator = getattr(self, "vision_coordinator", None)
        if coordinator is None:
            protocol = VisionProtocol(timeout_ms=VISION_OBSERVATION_TIMEOUT_MS)
            state_machine = VisionStateMachine(
                self._build_vision_state_config(),
                debug_sink=self._emit_vision_debug,
            )
            coordinator = VisionCoordinator(
                protocol=protocol, state_machine=state_machine
            )
            self.vision_coordinator = coordinator
        return coordinator

    def _ensure_uart_ingress(self):
        """返回 UART ingress 服务, 缺失时按当前依赖懒构造."""
        ingress = getattr(self, "uart_ingress", None)
        if ingress is None:
            ingress = UartIngressService(
                router=self._router,
                vision_coordinator=self._ensure_vision_coordinator(),
                build_context=self._build_handler_context,
                apply_command=self.apply_command,
                command_log=self._log_uart_command,
                emit_error=self._emit_error_log,
                now_ms=self._now_ms,
            )
            self.uart_ingress = ingress
        elif hasattr(ingress, "vision_coordinator"):
            ingress.vision_coordinator = self._ensure_vision_coordinator()
        return ingress

    # Command handling ----------------------------------------------

    def apply_command(self, line, source="uart6"):
        """接收并分发原始命令行字符串到各命令处理器.

        reset 指令优先处理(不受锁定影响);其余指令在锁定时忽略.

        参数:
            line: 原始命令行,如 "vx=10,vy=5" 或 "reset".
        """
        if not line:
            return
        self._router.route(line, self._build_handler_context(source=source))
