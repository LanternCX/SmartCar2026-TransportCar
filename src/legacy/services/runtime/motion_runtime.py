"""底盘与控制链运行时 owner."""

from control.attitude_estimator import AttitudeEstimator
from control.chassis_controller import ChassisController
from control.chassis_state import ChassisState
from control.kinematics import Odometry, OmniKinematics
from control.motion_planner import MotionPlanner
from control.pid_controller import PositionalPIDController, SpeedPIDController
from control.wheel import build_wheel_state
from control.wheel_speed_controller import WheelSpeedController
from filters.diff_limit_filter import DiffLimitFilter
from filters.lowpass_filter import LowPassFilter
from filters.spike_filter import SpikeMedianFilter
from utils.quaternion import Quaternion
from config.params import (
    AUTO_OMEGA_MAX,
    GYRO_LPF_ALPHA,
    GYRO_OFFSET_FILE,
    IDENT_RESULTS_FILE,
    MAX_DUTY,
    TICK_MS,
    YAW_I_MAX,
    YAW_KI,
    YAW_KP,
)
from hardware.encoders import create_encoders
from hardware.imu import create_imu
from hardware.motors import create_motors
from storage.param_manager import load_gyro_offsets, load_ident_lookup


class NullImu:
    """安全模式下使用的空 IMU."""

    def get(self):
        """返回全零六轴数据."""
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class NullEncoder:
    """安全模式下使用的空编码器."""

    def get(self):
        """返回零脉冲."""
        return 0.0


class NullMotor:
    """安全模式下使用的空电机."""

    def __init__(self):
        """初始化空电机占空比记录."""
        self.last_duty = 0

    def duty(self, value):
        """记录占空比但不触发真实输出."""
        self.last_duty = int(value)


def create_null_encoders():
    """构造三轮空编码器集合."""
    return {"m": NullEncoder(), "l": NullEncoder(), "r": NullEncoder()}


def create_null_motors():
    """构造三轮空电机集合."""
    return {"m": NullMotor(), "l": NullMotor(), "r": NullMotor()}


class MotionRuntime:
    """持有底盘状态、硬件句柄和控制链 owner."""

    def __init__(
        self,
        diagnostic_mode=False,
        uart_writer=None,
        create_imu_func=create_imu,
        create_motors_func=create_motors,
        create_encoders_func=create_encoders,
        load_ident_lookup_func=load_ident_lookup,
        load_gyro_offsets_func=load_gyro_offsets,
    ) -> None:
        self.diagnostic_mode = bool(diagnostic_mode)
        if self.diagnostic_mode:
            self.imu = NullImu()
            self.motors = create_null_motors()
            self.encoders = create_null_encoders()
        else:
            self.imu = create_imu_func()
            self.motors = create_motors_func()
            self.encoders = create_encoders_func()
        self.ident_lookup = load_ident_lookup_func(IDENT_RESULTS_FILE)
        imu_offsets = load_gyro_offsets_func(GYRO_OFFSET_FILE)
        imu_data = self.imu.get()

        gyro_lpf = LowPassFilter(alpha=GYRO_LPF_ALPHA, initial=0.0)
        q_est = Quaternion()
        kinematics = OmniKinematics()
        odometry = Odometry()
        yaw_pid = PositionalPIDController(
            output_limit=AUTO_OMEGA_MAX, integral_limit=YAW_I_MAX
        )
        yaw_pid.set_gains(YAW_KP, YAW_KI, 0.0)

        wheel_states = []
        for name in ("m", "l", "r"):
            gain_tau = self.ident_lookup.get(name, (None, None))
            controller = SpeedPIDController(
                output_limit=MAX_DUTY,
                plant_gain=gain_tau[0],
                plant_tau=gain_tau[1],
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

        self.chassis_state = ChassisState(
            wheel_states=wheel_states,
            target_speeds={"m": 0.0, "l": 0.0, "r": 0.0},
            yaw_pid=yaw_pid,
            heading_est=0.0,
            heading_target=0.0,
            yaw_integral=0.0,
            odometry=odometry,
            kinematics=kinematics,
            gyro_lpf=gyro_lpf,
            q_est=q_est,
            last_yaw_rad=0.0,
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
            uart_writer=uart_writer,
        )

    @property
    def controller(self):
        """返回底盘控制器兼容别名."""
        return self.chassis_controller
