"""辅车跨周期状态入口.

@file src/assistant/state/__init__.py
"""

from typing import Callable, Optional, Tuple


class AssistantState:
    """保存辅车跨周期最小运行状态."""

    def __init__(self):
        self.follow_active = False
        self.state_label = "IDLE"
        self.last_seq = 0
        self.odom = [0.0, 0.0]
        self.heading_deg = 0.0
        self.target_heading_deg = 0.0
        self.yaw_rate_deg_s = 0.0
        self.base_ok = False
        self.velocity_command = (0.0, 0.0, 0.0)
        self.timeout = False
        self.last_error = ""


class AssistantControlState:
    """保存辅车控制链跨周期内部状态."""

    def __init__(
        self,
        q_est=None,
        kinematics=None,
        odometry=None,
        gyro_lpf=None,
        wheel_filters=None,
        wheel_controllers=None,
    ):
        self.yaw_integral = 0.0
        self.heading_target_ready = False
        self.follow_target_world = None
        self.wheel_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.target_wheel_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.motor_duties = {"m": 0, "l": 0, "r": 0}
        self.q_est = q_est
        self.kinematics = kinematics
        self.odometry = odometry
        self.gyro_lpf = gyro_lpf
        self.wheel_filters = wheel_filters if wheel_filters is not None else {}
        self.wheel_controllers = (
            wheel_controllers if wheel_controllers is not None else {}
        )
        self.last_yaw_rad = 0.0


class MotionRuntimeState(AssistantState):
    """辅车过程式主线使用的运行时状态容器."""

    def __init__(self):
        AssistantState.__init__(self)
        self.control = AssistantControlState()
        self.hw_bundle = None
        self.safety: Optional[object] = None
        self.pid_map = {}
        self.speed_filter_window = 0
        self.speed_diff_max_delta = 0.0
        self.gyro_lpf_alpha = 0.0
        self.heading_hold_enabled = True
        self.yaw_kp = 0.0
        self.yaw_ki = 0.0
        self.yaw_i_max = 0.0
        self.auto_omega_max = 0.0
        self.follow_position_kp = 0.0
        self.follow_position_max_speed = 0.0
        self.tick_ms = 0
        self.tick_s = 0.0
        self.gyro_scale = 1.0
        self.ident_lookup = {}
        self.imu_offsets: Tuple[float, float, float, float, float, float] = (
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )
        self.encoder_ticks = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.imu_calibrated = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._last_cycle_token = None
        self._last_base_snapshot = None
        self._last_control_cycle_token = None
        self.state_line: Optional[Callable[[], str]] = None

    @property
    def yaw_integral(self):
        return self.control.yaw_integral

    @yaw_integral.setter
    def yaw_integral(self, value):
        self.control.yaw_integral = value

    @property
    def heading_target_ready(self):
        return self.control.heading_target_ready

    @heading_target_ready.setter
    def heading_target_ready(self, value):
        self.control.heading_target_ready = value

    @property
    def follow_target_world(self):
        return self.control.follow_target_world

    @follow_target_world.setter
    def follow_target_world(self, value):
        self.control.follow_target_world = value

    @property
    def wheel_speeds(self):
        return self.control.wheel_speeds

    @wheel_speeds.setter
    def wheel_speeds(self, value):
        self.control.wheel_speeds = value

    @property
    def target_wheel_speeds(self):
        return self.control.target_wheel_speeds

    @target_wheel_speeds.setter
    def target_wheel_speeds(self, value):
        self.control.target_wheel_speeds = value

    @property
    def motor_duties(self):
        return self.control.motor_duties

    @motor_duties.setter
    def motor_duties(self, value):
        self.control.motor_duties = value

    @property
    def q_est(self):
        return self.control.q_est

    @q_est.setter
    def q_est(self, value):
        self.control.q_est = value

    @property
    def kinematics(self):
        return self.control.kinematics

    @kinematics.setter
    def kinematics(self, value):
        self.control.kinematics = value

    @property
    def odometry(self):
        return self.control.odometry

    @odometry.setter
    def odometry(self, value):
        self.control.odometry = value

    @property
    def gyro_lpf(self):
        return self.control.gyro_lpf

    @gyro_lpf.setter
    def gyro_lpf(self, value):
        self.control.gyro_lpf = value

    @property
    def wheel_filters(self):
        return self.control.wheel_filters

    @wheel_filters.setter
    def wheel_filters(self, value):
        self.control.wheel_filters = value

    @property
    def wheel_controllers(self):
        return self.control.wheel_controllers

    @wheel_controllers.setter
    def wheel_controllers(self, value):
        self.control.wheel_controllers = value

    @property
    def last_yaw_rad(self):
        return self.control.last_yaw_rad

    @last_yaw_rad.setter
    def last_yaw_rad(self, value):
        self.control.last_yaw_rad = value
