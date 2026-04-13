"""搬运车控制单例封装,拆出原 remote_control.py 的全部逻辑."""

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
from hardware.uart_bus import create_uart3, create_uart6
from hardware.motors import create_motors
from hardware.encoders import create_encoders
from hardware.imu import create_imu
from storage.param_manager import load_ident_lookup, load_gyro_offsets
from services.command_router import router as _cmd_router
from services.command_policy import (
    build_command_health_fields,
    finalize_command_route,
)
from services.vision_protocol import VisionProtocol
from services.vision_state_machine import (
    SMState,
    VisionMachineInputs,
    VisionStateConfig,
    VisionStateMachine,
    resolve_relative_intent,
)
import services.commands as _commands  # noqa: F401 自动发现,所有 @router.command() 装饰器在此执行


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
VISION_OBSERVATION_TIMEOUT_MS = getattr(_params, "VISION_OBSERVATION_TIMEOUT_MS")
VISION_TARGET_X_PX = getattr(_params, "VISION_TARGET_X_PX")
VISION_TARGET_Y_PX = getattr(_params, "VISION_TARGET_Y_PX")
VISION_ANGLE_KP = getattr(_params, "VISION_ANGLE_KP")
VISION_DIST_KP = getattr(_params, "VISION_DIST_KP")
VISION_DX_KP = getattr(_params, "VISION_DX_KP")
VISION_PUSH_DX_KP = getattr(_params, "VISION_PUSH_DX_KP")
VISION_PUSH_DY_M = getattr(_params, "VISION_PUSH_DY_M")
VISION_PUSH_DISTANCE_M = getattr(_params, "VISION_PUSH_DISTANCE_M")
VISION_PUSH_ANGLE_DEG = getattr(_params, "VISION_PUSH_ANGLE_DEG")
VISION_ANGLE_DEADZONE_PX = getattr(_params, "VISION_ANGLE_DEADZONE_PX")
VISION_ANGLE_REENTRY_PX = getattr(_params, "VISION_ANGLE_REENTRY_PX")
VISION_DIST_DEADZONE_PX = getattr(_params, "VISION_DIST_DEADZONE_PX")
VISION_DX_DEADZONE_PX = getattr(_params, "VISION_DX_DEADZONE_PX")
VISION_HEADING_TOLERANCE_DEG = getattr(_params, "VISION_HEADING_TOLERANCE_DEG")
VISION_STABLE_FRAMES = getattr(_params, "VISION_STABLE_FRAMES")
VISION_MAX_DX_M = getattr(_params, "VISION_MAX_DX_M")
VISION_MAX_DY_M = getattr(_params, "VISION_MAX_DY_M")
VISION_MAX_D_ANGLE_DEG = getattr(_params, "VISION_MAX_D_ANGLE_DEG")
VISION_DONE_HOLD_MS = getattr(_params, "VISION_DONE_HOLD_MS")


VISION_STATE_NAMES = {
    SMState.IDLE: "IDLE",
    SMState.ALIGN_ANGLE: "ALIGN_ANGLE",
    SMState.ALIGN_DIST: "ALIGN_DIST",
    SMState.ALIGN_DX: "ALIGN_DX",
    SMState.ORBITING: "ORBITING",
    SMState.PUSHING: "PUSHING",
    SMState.RETURNING: "RETURNING",
    SMState.DONE: "DONE",
}


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
        startup_log("transport_car", "init start")

        # 板载 LED 与停止开关
        self.led = Pin("C4", Pin.OUT, value=True)
        self.switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
        self.switch2_init = self.switch2.value()

        # 串口(保持原波特率与编号)
        self.uart3 = create_uart3()
        self.uart6 = create_uart6()
        startup_log("transport_car", "uart ready")

        # IMU 初始化
        if self.diagnostic_mode:
            startup_log("transport_car", "diagnostic mode skip IMU init")
            self.imu = _NullImu()
        else:
            startup_log("transport_car", "IMU init start")
            self.imu = create_imu()
            startup_log("transport_car", "IMU ready")
        self.imu_data = self.imu.get()

        # 滤波与姿态估计状态
        self.gyro_lpf = LowPassFilter(alpha=GYRO_LPF_ALPHA, initial=0.0)
        self.heading_est = 0.0
        self.q_est = Quaternion()
        self.last_yaw_rad = 0.0

        # 偏航角姿态 PID(位置式,输出角速度)
        self.yaw_pid = PositionalPIDController(
            output_limit=AUTO_OMEGA_MAX, integral_limit=YAW_I_MAX
        )
        self.yaw_pid.set_gains(YAW_KP, YAW_KI, 0.0)
        self.yaw_integral = 0.0  # 保留字段便于调试显示

        # 运动学与里程计
        self.kinematics = OmniKinematics()
        self.odometry = Odometry()

        # Heading targets
        self.heading_target = 0.0

        # Motors and encoders
        if self.diagnostic_mode:
            startup_log("transport_car", "diagnostic mode skip motor/encoder init")
            self.motors = _create_null_motors()
            self.encoders = _create_null_encoders()
        else:
            startup_log("transport_car", "motor/encoder init start")
            self.motors = create_motors()
            self.encoders = create_encoders()
            startup_log("transport_car", "motor/encoder ready")

        # 辨识参数加载
        startup_log("transport_car", "loading calibration data")
        self.ident_lookup = load_ident_lookup(IDENT_RESULTS_FILE)

        # IMU 零偏加载
        self.imu_offsets = load_gyro_offsets(
            GYRO_OFFSET_FILE,
            logger=lambda msg: startup_log("transport_car", msg),
        )

        # 轮组状态构造:滤波、PID、编码器/电机封装
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

        # 运行期状态
        self.pit_flag = False
        self.tick_count = 0
        self.target_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self.command_lock = False
        self.command_mode = "none"
        self.lock_start_time = 0
        self.rear_only_mode = False
        self.last_rear_mode = False
        self.rx_buf3 = ""
        self.rx_buf6 = ""

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

        # 相对位移暂存(供 _finalize_route 使用)
        self._pending_dx = None
        self._pending_dy = None
        self._pending_d_angle = None
        self._pending_lock = None
        self._rear_mode_changed = False

        # 初始化三轮 PID 增益(与旧版一致)
        self.init_pid()

        # 命令路由器:使用单例路由器(命令模块已通过 @router 装饰器完成注册)
        self._router = _cmd_router

        # 视觉协议与状态机
        self.vision_protocol = VisionProtocol(timeout_ms=VISION_OBSERVATION_TIMEOUT_MS)
        self.vision_state_machine = VisionStateMachine(
            self._build_vision_state_config()
        )
        self._vision_step_result = None
        self._vision_resolved_target = None
        startup_log("transport_car", "init complete")

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
            target_x_px=VISION_TARGET_X_PX,
            target_y_px=VISION_TARGET_Y_PX,
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

    def _now_ms(self):
        """返回当前毫秒时间戳,兼容主机测试环境."""
        ticks_ms = getattr(time, "ticks_ms", None)
        if ticks_ms is not None:
            return int(ticks_ms())
        return int(time.time() * 1000)

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
        if not self._boot_step_logged:
            startup_log("transport_car", "step loop active")
            self._boot_step_logged = True

        if self.pit_flag:
            if not self._boot_tick_logged:
                startup_log("transport_car", "first ticker event received")
                self._boot_tick_logged = True
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
        reset_pi_state(self.wheel_states)
        for state in self.wheel_states:
            state["motor"].duty(0)
        self.uart3.write("stop\r\n")

    def _handle_uart_line(self, line, source):
        """按来源处理单行串口输入."""
        if not line:
            return

        if line.startswith("?"):
            self._router.handle_query(line[1:], self, source=source)
            return

        if source == "uart6":
            observation = self.vision_protocol.try_parse_observation(
                line, source=source, now_ms=self._now_ms()
            )
            if observation is not None:
                return

        self.apply_command(line)

    def _refresh_vision_target(self, now_ms=None):
        """推进视觉状态机并刷新当前视觉目标."""
        if now_ms is None:
            now_ms = self._now_ms()

        if self.command_lock:
            self.vision_protocol.clear()
            self.vision_state_machine.reset()
            self._vision_step_result = None
            self._vision_resolved_target = None
            return

        observation = self.vision_protocol.get_observation(now_ms)
        inputs = VisionMachineInputs(
            observation=observation,
            heading_deg=self.heading_est,
            odom_x=self.odometry.x,
            odom_y=self.odometry.y,
            now_ms=now_ms,
        )
        self._vision_step_result = self.vision_state_machine.step(inputs)
        self._vision_resolved_target = resolve_relative_intent(
            self._vision_step_result.intent,
            odom_x=self.odometry.x,
            odom_y=self.odometry.y,
            heading_deg=self.heading_est,
        )

    def _get_active_position_targets(self):
        """返回当前激活控制源的位置目标."""
        if self._vision_resolved_target is not None:
            return self._vision_resolved_target.x, self._vision_resolved_target.y
        return self.last_cmd.get("x"), self.last_cmd.get("y")

    def _get_active_angle_command(self):
        """返回当前激活控制源的角度目标."""
        if self._vision_resolved_target is not None:
            return self._vision_resolved_target.angle_deg
        return self.last_cmd.get("angle")

    def _get_active_rear_only_mode(self):
        """返回当前激活控制源的后轮模式."""
        if self._vision_resolved_target is not None:
            return self._vision_resolved_target.rear_only_mode
        return self.rear_only_mode

    def _get_vision_state_name(self):
        """返回当前视觉状态机状态名."""
        state = getattr(self.vision_state_machine, "state", None)
        if state is None:
            return "UNKNOWN"
        return VISION_STATE_NAMES.get(int(state), "UNKNOWN")

    def build_health_snapshot(self):
        """构造系统健康摘要快照."""
        snapshot = {
            "alive": 1,
            "uptime_ms": max(0, self._now_ms() - int(self.boot_time_ms)),
            "last_err": self.last_exception_text,
            "vision_state": self._get_vision_state_name(),
        }
        snapshot.update(build_command_health_fields(self))
        return snapshot

    def get_query_uart(self):
        """返回当前查询响应应写入的串口."""
        return getattr(self, "_query_response_uart", self.uart6)

    def build_tick_snapshot(self):
        """构造控制周期统计快照."""
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
        """构造 IMU 相关诊断快照."""
        return {
            "ok": 1 if self.imu_data else 0,
            "yaw_deg": float(self.heading_est),
            "yaw_rate_dps": float(self._yaw_rate),
            "gz_raw": float(self._last_gz_raw),
        }

    def build_encoder_snapshot(self):
        """构造编码器观测快照."""
        snapshot = {}
        for state in self.wheel_states:
            name = state["name"]
            snapshot["%s_raw" % name] = float(state.get("raw_speed", 0.0))
            snapshot["%s_filt" % name] = float(state.get("filtered_speed", 0.0))
        return snapshot

    def build_motor_snapshot(self):
        """构造电机目标与占空比快照."""
        snapshot = {}
        for state in self.wheel_states:
            name = state["name"]
            snapshot["%s_target" % name] = float(self.target_speeds.get(name, 0.0))
            snapshot["%s_duty" % name] = float(state.get("duty", 0.0))
        snapshot["rear"] = 1 if self._get_active_rear_only_mode() else 0
        return snapshot

    def build_vision_snapshot(self):
        """构造视觉观测与解析目标快照."""
        observation = self.vision_protocol.get_observation(now_ms=self._now_ms())
        snapshot = {
            "state": self._get_vision_state_name(),
            "obs_age_ms": None,
            "obs_x": None,
            "obs_y": None,
            "target_x": None,
            "target_y": None,
            "target_angle": None,
        }
        if observation is not None:
            snapshot["obs_age_ms"] = self._now_ms() - int(observation.timestamp_ms)
            snapshot["obs_x"] = float(observation.x)
            snapshot["obs_y"] = float(observation.y)
        if self._vision_resolved_target is not None:
            snapshot["target_x"] = float(self._vision_resolved_target.x)
            snapshot["target_y"] = float(self._vision_resolved_target.y)
            snapshot["target_angle"] = float(self._vision_resolved_target.angle_deg)
        return snapshot

    # Internal helpers ----------------------------------------------
    def init_pid(self):
        """按 PID_MAP 配置表初始化三轮速度环增益."""
        for state in self.wheel_states:
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
        # 三轮 Y 车模逆运动学
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
        self._update_wheel_speeds()
        self._update_attitude(dt_s)
        self._run_control(dt_s)

    def _update_wheel_speeds(self):
        """读取编码器脉冲并通过多级滤波器处理.

        依次执行:中值滤波(去尖刺)→ 差分限幅(限突变)→ 双窗回归(融合)→ 低通(平滑).
        结果存储在 state["filtered_speed"].
        """
        for state in self.wheel_states:
            # 原始脉冲数(每周期)
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            # 中值滤波抑制尖刺
            smooth_raw = state["input_lpf"].update(raw)
            # 差分限幅限制突变速度
            smooth_raw = state["diff_filter"].update(smooth_raw)
            # 双窗线性回归融合
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            # 输出端低通,得到平滑速度
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)

    def _update_attitude(self, dt_s):
        """更新 IMU 数据、四元数积分、解包偏航角、计算滤波角速度.

        参数:
            dt_s: 时间增量(秒).

        副作用:
            修改 self.q_est、self.last_yaw_rad、self.heading_est 等姿态状态.
        """
        # 每个周期刷新 IMU 数据(capture_list 触发设备更新)
        self.imu_data = self.imu.get()
        if self.imu_data:
            # 去除零偏,得到原始角速度 LSB
            gx_raw = float(self.imu_data[3]) - self.imu_offsets[3]
            gy_raw = float(self.imu_data[4]) - self.imu_offsets[4]
            gz_raw = float(self.imu_data[5]) - self.imu_offsets[5]
        else:
            gx_raw = gy_raw = gz_raw = 0.0
        self._last_gz_raw = gz_raw

        # LSB -> rad/s,后续四元数积分使用
        rad_scale = (math.pi / 180.0) / GYRO_SCALE
        gx = gx_raw * rad_scale
        gy = gy_raw * rad_scale
        gz = gz_raw * rad_scale

        # 四元数积分更新姿态
        self.q_est.update(gx, gy, gz, dt_s)

        # 解算并解包 yaw,保持连续角度
        curr_yaw_rad = self.q_est.to_euler_yaw()
        delta_yaw = curr_yaw_rad - self.last_yaw_rad
        if delta_yaw > math.pi:
            delta_yaw -= 2.0 * math.pi
        elif delta_yaw < -math.pi:
            delta_yaw += 2.0 * math.pi
        self.last_yaw_rad = curr_yaw_rad

        # 角速度低通后用于姿态控制
        yaw_rate = self.gyro_lpf.update(gz * (180.0 / math.pi))

        # 读取三轮滤波后的脉冲速度
        vm_pulse = self.wheel_states[0]["filtered_speed"]
        vl_pulse = self.wheel_states[1]["filtered_speed"]
        vr_pulse = self.wheel_states[2]["filtered_speed"]

        # 脉冲速度 -> m/s
        vm_mps = self.kinematics.velocity_pulses_to_m_s(vm_pulse, dt_s)
        vl_mps = self.kinematics.velocity_pulses_to_m_s(vl_pulse, dt_s)
        vr_mps = self.kinematics.velocity_pulses_to_m_s(vr_pulse, dt_s)

        # 前向运动学,得到车体系速度
        vx_rob_mps, vy_rob_mps, _ = self.kinematics.forward_kinematics(
            vm_mps, vl_mps, vr_mps
        )

        # 使用当前估计航向更新里程计
        self.odometry.update(
            vx_rob_mps, vy_rob_mps, math.radians(self.heading_est), dt_s
        )
        # 积分更新航向角(度)
        self.heading_est += math.degrees(delta_yaw)

        # 存储滤波后的角速度供姿态控制使用
        self._yaw_rate = yaw_rate

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
        cmd_angle = self._get_active_angle_command()
        if self._vision_resolved_target is not None:
            cmd_omega = None
        else:
            cmd_omega = self.last_cmd.get("omega")

        if cmd_angle is not None:
            # 角度模式:目标为绝对角度,PID 产出角速度
            self.heading_target = cmd_angle
            omega_pid = self.yaw_pid.update(self.heading_target, self.heading_est, dt_s)
            omega_auto = omega_pid - YAW_KD * self._yaw_rate
            omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)

        elif cmd_omega is not None:
            # 角速度模式:直接跟随 omega,若极小则进入保持角度
            omega_cmd = cmd_omega
            if abs(omega_cmd) < HOLD_SPEED_EPS:
                omega_pid = self.yaw_pid.update(
                    self.heading_target, self.heading_est, dt_s
                )
                omega_auto = omega_pid - YAW_KD * self._yaw_rate
                omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)
            else:
                # 速度模式非零时重置目标角到当前,清积分
                self.heading_target = self.heading_est
                self.yaw_pid.reset()
                self.yaw_integral = 0.0
        else:
            # 保持模式:目标角保持不变,PID 输出角速度
            omega_pid = self.yaw_pid.update(self.heading_target, self.heading_est, dt_s)
            omega_auto = omega_pid - YAW_KD * self._yaw_rate
            omega_cmd = clamp(omega_auto, -AUTO_OMEGA_MAX, AUTO_OMEGA_MAX)

        # 同步积分值,便于调试与兼容旧接口
        if hasattr(self.yaw_pid, "integral"):
            self.yaw_integral = self.yaw_pid.integral

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
        target_vx_cmd = 0.0
        target_vy_cmd = 0.0

        cmd_x, cmd_y = self._get_active_position_targets()

        if cmd_x is not None or cmd_y is not None:
            # 位置模式:取目标点,缺省坐标补 0
            t_x = cmd_x if cmd_x is not None else 0.0
            t_y = cmd_y if cmd_y is not None else 0.0

            err_x = t_x - self.odometry.x
            err_y = t_y - self.odometry.y

            # 世界系 P 控制得到线速度
            v_world_x = err_x * POS_KP
            v_world_y = err_y * POS_KP

            # 限制平面速度上限
            v_speed = math.sqrt(v_world_x * v_world_x + v_world_y * v_world_y)
            if v_speed > POS_MAX_SPEED:
                scale = POS_MAX_SPEED / v_speed
                v_world_x *= scale
                v_world_y *= scale

            # 旋转到车体系
            t_rad = math.radians(self.heading_est)
            cos_t = math.cos(t_rad)
            sin_t = math.sin(t_rad)

            vx_rob_ctrl = v_world_x * cos_t + v_world_y * sin_t
            vy_rob_ctrl = -v_world_x * sin_t + v_world_y * cos_t

            # m/s -> 脉冲,乘 3 保持与逆解内部除 3 对应
            vx_pulses = self.kinematics.velocity_m_s_to_pulses(vx_rob_ctrl, dt_s)
            vy_pulses = self.kinematics.velocity_m_s_to_pulses(vy_rob_ctrl, dt_s)

            target_vx_cmd = vx_pulses * 3.0
            target_vy_cmd = vy_pulses * 3.0

        else:
            # 速度模式直接使用命令值
            target_vx_cmd = float(self.last_cmd.get("vx", 0.0))
            target_vy_cmd = float(self.last_cmd.get("vy", 0.0))

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
        # 逆运动学 -> 三轮目标脉冲速度
        vm, vl, vr = self._inverse_kinematics(
            target_vx_cmd,
            target_vy_cmd,
            float(omega_cmd),
        )

        if self._get_active_rear_only_mode():
            # 仅后轮:前两轮停,后轮减速 1/3 与旧版一致
            self.target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX) / 3
            self.target_speeds["l"] = 0.0
            self.target_speeds["r"] = 0.0
        else:
            # 全向模式:三轮分别限幅
            self.target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
            self.target_speeds["l"] = clamp(vl, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
            self.target_speeds["r"] = clamp(vr, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)

        # 速度环 PID 输出占空比
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
                # 未启用的轮直接清零
                state["controller"].reset()
                state["duty"] = 0.0
                state["motor"].duty(0)

    def _check_unlock(self):
        """在锁定模式下检查角度/位置误差,达标时解锁.

        当角度误差 < ANGLE_TOLERANCE 且位置误差 < POS_TOLERANCE 时,
        退出锁定模式.若启用后轮模式,解锁后自动回归全向并停车.

        副作用:
            修改 self.command_lock、self.rear_only_mode、self.target_speeds.
        """
        if not self.command_lock:
            return

        angle_ok = True
        if self.last_cmd.get("angle") is not None:
            err_angle = abs(self.heading_target - self.heading_est)
            if err_angle > ANGLE_TOLERANCE:
                angle_ok = False

        pos_ok = True
        if self.last_cmd.get("x") is not None or self.last_cmd.get("y") is not None:
            tx_chk = self.last_cmd.get("x")
            ty_chk = self.last_cmd.get("y")
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
                # 后轮模式完成后自动回全向并停车
                self.rear_only_mode = False
                self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
                reset_pi_state(self.wheel_states)
                self.yaw_pid.reset()
                self.yaw_integral = 0.0
                self.heading_target = self.heading_est
                for state in self.wheel_states:
                    state["motor"].duty(0)
                    state["duty"] = 0.0

    def _process_uart(self):
        """轮询两个串口:处理查询和运动指令.

        UART3:收集调试命令(来自 RTT 或其他监控工具).
        UART6:收集远程操控命令.
        两个串口均支持查询指令(前缀 "?")和控制指令(key=val 格式).

        异常时向串口回写错误信息.
        """
        buf_len = self.uart3.any()
        if buf_len:
            try:
                self.rx_buf3 += self.uart3.read(buf_len).decode()
                while True:
                    idx = self.rx_buf3.find("\n")
                    if idx == -1:
                        break
                    line = self.rx_buf3[:idx].rstrip("\r").strip()
                    self.rx_buf3 = self.rx_buf3[idx + 1 :]
                    self._handle_uart_line(line, source="uart3")
            except Exception as exc:
                self.last_exception_text = str(exc)
                self.uart3.write("ERR %s\r\n" % exc)

        buf_len = self.uart6.any()
        if buf_len:
            try:
                self.rx_buf6 += self.uart6.read(buf_len).decode()
                while True:
                    idx = self.rx_buf6.find("\n")
                    if idx == -1:
                        break
                    line = self.rx_buf6[:idx].rstrip("\r").strip()
                    self.rx_buf6 = self.rx_buf6[idx + 1 :]
                    self._handle_uart_line(line, source="uart6")
            except Exception as exc:
                self.last_exception_text = str(exc)
                self.uart3.write("ERR %s\r\n" % exc)

    # Command handling ----------------------------------------------

    def apply_command(self, line):
        """接收并分发原始命令行字符串到各命令处理器.

        reset 指令优先处理(不受锁定影响);其余指令在锁定时忽略.

        参数:
            line: 原始命令行,如 "vx=10,vy=5" 或 "reset".
        """
        if not line:
            return
        self._router.route(line, self)

    def _finalize_route(self, dispatched):
        """在路由完成后处理跨 key 的后处理逻辑.

        包括相对位移(dx, dy)的世界系到车体系变换.

        参数:
            dispatched: 本次路由中分发的命令关键字集合.
        """
        finalize_command_route(self, dispatched, now_ms=self._now_ms())
