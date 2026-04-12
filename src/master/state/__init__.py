"""主车跨周期状态入口.

@file src/master/state/__init__.py
"""


class MasterRuntimeState:
    """保存主车跨周期业务状态."""

    def __init__(self):
        self.last_target = {"kind": "hold"}
        self.last_applied_target = {
            "kind": "hold",
            "vx": 0.0,
            "vy": 0.0,
            "omega": 0.0,
        }
        self.heading_deg = 0.0
        self.yaw_rate_deg_s = 0.0
        self.odom = [0.0, 0.0]
        self.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.imu_calibrated = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.encoder_ticks = {"m": 0.0, "l": 0.0, "r": 0.0}


class MasterControlState:
    """保存主车控制链跨周期内部状态."""

    def __init__(
        self,
        q_est=None,
        kinematics=None,
        odometry=None,
        gyro_lpf=None,
        wheel_filters=None,
        wheel_controllers=None,
    ):
        self.target_heading_deg = 0.0
        self.yaw_integral = 0.0
        self.heading_target_ready = False
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
        self.last_attitude_time_us = None


class MotionRuntimeState(MasterRuntimeState):
    """主车过程式运行时使用的状态对象.

    @brief 把控制链内部 owner 集中放在 `control` 下, 同时保留运行时主线可直接读写的扁平入口。
    """

    def __init__(self):
        MasterRuntimeState.__init__(self)
        self.control = MasterControlState()
        self.hw_bundle = None
        self._control_seq = 0
        self.pid_map = {}
        self.heading_hold_enabled = True
        self.yaw_kp = 0.0
        self.yaw_ki = 0.0
        self.yaw_kd = 0.0
        self.yaw_i_max = 0.0
        self.auto_omega_max = 0.0
        self.hold_speed_eps = 0.0
        self.tick_ms = 0
        self.tick_s = 0.0
        self.gyro_scale = 1.0
        self.ident_lookup = {}
        self.imu_offsets = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._last_cycle_token = None
        self._last_base_snapshot = None

    @property
    def target_heading_deg(self):
        return self.control.target_heading_deg

    @target_heading_deg.setter
    def target_heading_deg(self, value):
        self.control.target_heading_deg = value

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

    @property
    def last_attitude_time_us(self):
        return self.control.last_attitude_time_us

    @last_attitude_time_us.setter
    def last_attitude_time_us(self, value):
        self.control.last_attitude_time_us = value
