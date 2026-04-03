"""底盘运行态容器."""


class ChassisState:
    """集中持有底盘控制与状态估计相关运行时状态."""

    def __init__(
        self,
        wheel_states=None,
        target_speeds=None,
        yaw_pid=None,
        heading_est=0.0,
        heading_target=0.0,
        yaw_integral=0.0,
        odometry=None,
        kinematics=None,
        gyro_lpf=None,
        q_est=None,
        last_yaw_rad=0.0,
        imu=None,
        imu_data=None,
        imu_offsets=None,
        yaw_rate=0.0,
        last_gz_raw=0.0,
    ):
        self.wheel_states = wheel_states if wheel_states is not None else []
        self.target_speeds = (
            target_speeds
            if target_speeds is not None
            else {
                "m": 0.0,
                "l": 0.0,
                "r": 0.0,
            }
        )
        self.yaw_pid = yaw_pid
        self.heading_est = float(heading_est)
        self.heading_target = float(heading_target)
        self.yaw_integral = float(yaw_integral)
        self.odometry = odometry
        self.kinematics = kinematics
        self.gyro_lpf = gyro_lpf
        self.q_est = q_est
        self.last_yaw_rad = float(last_yaw_rad)
        self.imu = imu
        self.imu_data = imu_data
        self.imu_offsets = imu_offsets if imu_offsets is not None else [0.0] * 6
        self.yaw_rate = float(yaw_rate)
        self.last_gz_raw = float(last_gz_raw)
