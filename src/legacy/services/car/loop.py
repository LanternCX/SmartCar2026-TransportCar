"""@brief 搬运车控制循环与底盘控制 mixin.

@note
本模块只保留与 5ms 主循环强相关的编排逻辑, 不直接实现控制算法细节
"""

import gc

from config.params import PID_MAP, TICK_MS
from control.attitude_estimator import AttitudeEstimator
from control.chassis_controller import ChassisController
from control.chassis_state import ChassisState
from control.kinematics import OmniKinematics, Odometry
from control.motion_planner import MotionPlanner
from control.pid_math import reset_pi_state
from control.wheel_speed_controller import WheelSpeedController
from services.runtime.motion_runtime import NullImu


class _SwitchContract:
    """@brief 静态分析用的最小开关契约."""

    def value(self):
        return 0


class _TickerContract:
    """@brief 静态分析用的最小 ticker 契约."""

    def stop(self):
        return None


class _UartContract:
    """@brief 静态分析用的最小串口契约."""

    def write(self, _text):
        return None


class _LedContract:
    """@brief 静态分析用的最小 LED 契约."""

    def toggle(self):
        return None


class _SessionContract:
    """@brief 静态分析用的最小命令会话契约."""

    def __init__(self):
        self.last_cmd = {}
        self.command_lock = False
        self.rear_only_mode = False


class _LoopHost:
    """@brief 为静态分析声明 loop mixin 所需宿主接口.

    @note
    这些占位字段只服务静态分析, 不负责真实运行时状态所有权
    真实 owner 仍由 `RuntimeCore`, `MotionRuntime` 和 `CommandSession` 提供
    """

    pit_flag = False
    switch2 = _SwitchContract()
    switch2_init = 0
    ticker = _TickerContract()
    uart3 = _UartContract()
    led = _LedContract()
    last_time_us = 0
    last_loop_dt_us = 0
    max_loop_dt_us = 0
    loop_dt_total_us = 0
    loop_overrun_count = 0
    tick_count = 0
    command_session = _SessionContract()
    chassis_state = None
    chassis_controller = None

    def _process_uart(self):
        raise NotImplementedError

    def _refresh_vision_target(self, now_ms=None):
        raise NotImplementedError

    def _now_us(self):
        raise NotImplementedError

    def _ticks_diff_us(self, current_us, previous_us):
        raise NotImplementedError

    def _get_active_position_targets(self):
        raise NotImplementedError

    def _get_vision_resolved_target(self):
        raise NotImplementedError

    def _get_active_angle_command(self):
        raise NotImplementedError

    def _get_active_rear_only_mode(self):
        raise NotImplementedError


class LoopMixin(_LoopHost):
    """@brief 提供控制循环与底盘控制能力."""

    def step(self):
        """@brief 执行一次主循环步进.

        @return `True` 表示继续运行, `False` 表示应停止
        """

        # `pit_flag` 由中断回调置位, 这里只在主循环中兑现一次 tick 处理
        if self.pit_flag:
            self._handle_tick()
            self.pit_flag = False
        self._process_uart()
        if self.switch2.value() != self.switch2_init:
            self.stop()
            return False
        gc.collect()
        return True

    def stop(self):
        """@brief 停止控制循环并清零电机输出."""

        # stop 不只停 ticker, 还必须把速度环残留积分和 duty 一并清掉
        if self.ticker:
            self.ticker.stop()
        chassis_state = self.chassis_state
        wheel_states = (
            [] if chassis_state is None else (chassis_state.wheel_states or [])
        )
        reset_pi_state(wheel_states)
        for state in wheel_states:
            state["motor"].duty(0)
        self.uart3.write("stop\r\n")

    def init_pid(self):
        """@brief 按配置表初始化三轮速度环增益."""
        chassis_state = self.chassis_state
        if chassis_state is None:
            return
        for state in chassis_state.wheel_states or []:
            kp_val, ki_val, ki2_val = PID_MAP.get(state["name"], (10.0, 0.5, 0.01))
            state["kp"], state["ki"] = kp_val, ki_val
            state["controller"].set_gains(kp_val, ki_val, ki2_val)

    def _inverse_kinematics(self, vx, vy, omega):
        """@brief 返回底盘控制器逆运动学结果."""
        return self._ensure_chassis_controller().inverse_kinematics(vx, vy, omega)

    def inverse_kinematics(self, vx, vy, omega):
        """@brief 返回公开逆运动学接口."""
        return self._inverse_kinematics(vx, vy, omega)

    def _handle_tick(self):
        """@brief 执行单次 5ms 控制周期.

        @note
        该入口按固定顺序完成: 视觉刷新 -> 计时统计 -> 控制调度
        不能在这里插入阻塞式 I/O
        """

        # 视觉目标在本拍开始时刷新, 保证后续控制量使用的是同一拍快照
        self._refresh_vision_target()
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
        controller = getattr(self, "chassis_controller", None)
        session = self.command_session
        if controller is None:
            # host 测试可能只提供最小底盘状态, 这里保留旧控制路径兜底
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
        if not hasattr(controller, "state"):
            return
        if tick_result is not None:
            session.command_lock, session.rear_only_mode, session.last_cmd = tick_result

    def _build_chassis_controller(self):
        """@brief 按当前宿主状态懒构造底盘控制器.

        @return `ChassisController`
        """

        # 若测试通过 `__new__` 构造最小对象, 这里需要自行补齐一套可工作的底盘状态
        state = getattr(self, "_chassis_state", None)
        if state is None:
            kinematics = OmniKinematics()
            state = ChassisState(
                wheel_states=[],
                target_speeds={"m": 0.0, "l": 0.0, "r": 0.0},
                odometry=Odometry(),
                kinematics=kinematics,
                imu=NullImu(),
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
        """@brief 返回底盘控制器, 缺失时懒创建.

        @return `ChassisController`
        """
        controller = getattr(self, "chassis_controller", None)
        if controller is None:
            controller = self._build_chassis_controller()
            self.chassis_controller = controller
            self.chassis_state = controller.state
        return controller

    def _update_wheel_speeds(self):
        """@brief 更新轮速估计."""
        self._ensure_chassis_controller().update_wheel_speeds()

    def _update_attitude(self, dt_s):
        """@brief 更新姿态估计.

        @param dt_s 控制周期秒数
        """
        self._ensure_chassis_controller().update_attitude(dt_s)

    def _run_control(self, dt_s):
        """@brief 执行一次完整控制调度.

        @param dt_s 控制周期秒数
        """
        omega_cmd = self._compute_omega_cmd(dt_s)
        target_vx_cmd, target_vy_cmd = self._compute_planar_targets(dt_s)
        self._apply_target_speeds(target_vx_cmd, target_vy_cmd, omega_cmd, dt_s)
        self._check_unlock()

    def _compute_omega_cmd(self, dt_s):
        """@brief 计算目标角速度.

        @param dt_s 控制周期秒数
        @return 目标角速度
        """
        cmd_omega = (
            None
            if self._get_vision_resolved_target() is not None
            else self.command_session.last_cmd.get("omega")
        )
        return self._ensure_chassis_controller().compute_omega_cmd(
            dt_s, self._get_active_angle_command(), cmd_omega
        )

    def _compute_planar_targets(self, dt_s):
        """@brief 计算车体系平面速度目标.

        @param dt_s 控制周期秒数
        @return `(vx, vy)` 目标二元组
        """
        active_target_x, active_target_y = self._get_active_position_targets()
        return self._ensure_chassis_controller().compute_planar_targets(
            dt_s, active_target_x, active_target_y, self.command_session.last_cmd
        )

    def _apply_target_speeds(self, target_vx_cmd, target_vy_cmd, omega_cmd, dt_s):
        """@brief 下发逆运动学与速度环目标.

        @param target_vx_cmd 车体 x 方向目标速度
        @param target_vy_cmd 车体 y 方向目标速度
        @param omega_cmd 目标角速度
        @param dt_s 控制周期秒数
        """
        self._ensure_chassis_controller().apply_target_speeds(
            target_vx_cmd,
            target_vy_cmd,
            omega_cmd,
            dt_s,
            self._get_active_rear_only_mode(),
        )

    def _check_unlock(self):
        """@brief 检查锁定模式是否可以自动解锁.

        @note
        解锁判据在 `ChassisController` 内部, 这里仅负责把命令会话结果回写到 owner
        """
        session = self.command_session
        session.command_lock, session.rear_only_mode, session.last_cmd = (
            self._ensure_chassis_controller().check_unlock(
                session.last_cmd,
                session.command_lock,
                session.rear_only_mode,
            )
        )
