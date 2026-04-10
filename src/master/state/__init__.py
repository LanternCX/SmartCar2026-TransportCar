"""主车跨周期状态入口.

@file src/master/state/__init__.py
"""


class MotionRuntimeState:
    """主车过程式运行时状态对象.

    @brief 当前主线只保留底座过程式入口需要的最小跨周期字段。
    """

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
        self.target_heading_deg = 0.0
        self.yaw_integral = 0.0
        self.heading_target_ready = False
        self.wheel_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.target_wheel_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.motor_duties = {"m": 0, "l": 0, "r": 0}
        self.q_est = None
        self.kinematics = None
        self.odometry = None
        self.gyro_lpf = None
        self.wheel_filters = {}
        self.wheel_controllers = {}
        self.last_yaw_rad = 0.0
        self.last_attitude_time_us = None
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
