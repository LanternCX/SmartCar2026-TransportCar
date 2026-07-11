"""`core.runtime` 测试公用桩与导入辅助."""

import importlib
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))


class CaptureUart:
    """最小串口桩, 用于记录写入并可选注入读取异常."""

    def __init__(self, incoming=b"", read_error=None) -> None:
        self.messages = []
        self._incoming = incoming
        self._read_error = read_error

    def write(self, text) -> None:
        self.messages.append(text)

    def any(self) -> int:
        return len(self._incoming)

    def read(self, _size):
        if self._read_error is not None:
            raise self._read_error
        data = self._incoming
        self._incoming = b""
        return data


class DummyMotor:
    """最小电机桩."""

    def __init__(self) -> None:
        self.duties = []

    def duty(self, value) -> None:
        self.duties.append(value)


class DummyPid:
    """最小 PID 桩."""

    def __init__(self) -> None:
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1


class RecordingController:
    """记录目标输入的最小控制器桩."""

    def __init__(self, return_value=0.0) -> None:
        self.return_value = return_value
        self.update_calls = []
        self.reset_count = 0

    def update(self, target, measured, dt_s):
        self.update_calls.append((target, measured, dt_s))
        return self.return_value

    def reset(self) -> None:
        self.reset_count += 1


class DummyTicker:
    """最小 ticker 桩."""

    def __init__(self) -> None:
        self.stop_count = 0

    def stop(self) -> None:
        self.stop_count += 1


class StubWheelState:
    """测试用固定轮状态."""

    def __init__(
        self,
        name="m",
        encoder=None,
        motor=None,
        controller=None,
        raw_speed=0.0,
        filtered_speed=0.0,
        duty=0.0,
    ) -> None:
        self.name = name
        self.encoder = encoder
        self.motor = motor
        self.controller = controller
        self.raw_speed = float(raw_speed)
        self.filtered_speed = float(filtered_speed)
        self.duty = float(duty)
        self.input_lpf = None
        self.diff_filter = None
        self.dual_filter = None
        self.output_lpf = None


def install_transport_car_stubs() -> None:
    """安装 `core.runtime` 在主机侧测试所需的最小依赖桩."""
    module_names = [
        "machine",
        "control.wheel",
        "control.pid_controller",
        "control.pid_math",
        "control.kinematics",
        "filters.lowpass_filter",
        "filters.spike_filter",
        "filters.diff_limit_filter",
        "utils.quaternion",
        "utils.startup_log",
        "hardware.uart_bus",
        "hardware.motors",
        "hardware.encoders",
        "hardware.imu",
        "storage.param_manager",
        "config.motion",
        "config.vision",
        "config.safety",
        "config.comm",
        "config.storage",
    ]
    for name in module_names:
        sys.modules.pop(name, None)

    machine = ModuleType("machine")

    class Pin:
        OUT = "out"
        IN = "in"
        PULL_UP_47K = "pull_up"

        def __init__(self, *_args, **_kwargs) -> None:
            self._value = _kwargs.get("value", 0)

        def value(self):
            return self._value

        def toggle(self) -> None:
            return None

    setattr(machine, "Pin", Pin)
    sys.modules["machine"] = machine

    control_wheel = ModuleType("control.wheel")
    setattr(
        control_wheel,
        "build_wheel_state",
        lambda *args, **kwargs: StubWheelState(
            name=args[0],
            encoder=args[1],
            motor=args[2],
            controller=kwargs["pid_controller"],
        ),
    )
    sys.modules["control.wheel"] = control_wheel

    control_pid_controller = ModuleType("control.pid_controller")

    class _SpeedPidController:
        def __init__(self, *args, **kwargs) -> None:
            self.integral = 0.0

        def set_gains(self, *_args) -> None:
            return None

        def update(self, *_args) -> float:
            return 0.0

        def reset(self) -> None:
            return None

    class _PositionalPidController(_SpeedPidController):
        pass

    setattr(control_pid_controller, "SpeedPIDController", _SpeedPidController)
    setattr(control_pid_controller, "PositionalPIDController", _PositionalPidController)
    sys.modules["control.pid_controller"] = control_pid_controller

    control_pid_math = ModuleType("control.pid_math")
    setattr(
        control_pid_math,
        "clamp",
        lambda value, low, high: max(low, min(high, value)),
    )
    setattr(control_pid_math, "reset_pi_state", lambda _wheel_states: None)
    sys.modules["control.pid_math"] = control_pid_math

    control_kinematics = ModuleType("control.kinematics")

    class _OmniKinematics:
        def velocity_pulses_to_m_s(self, value, _dt_s) -> float:
            return float(value)

        def velocity_m_s_to_pulses(self, value, _dt_s) -> float:
            return float(value)

        def forward_kinematics(self, vm, vl, vr):
            return float(vm), float(vl), float(vr)

    class _Odometry:
        def __init__(self, x_scale=1.0, y_scale=1.0) -> None:
            self.x = 0.0
            self.y = 0.0
            self.x_scale = float(x_scale)
            self.y_scale = float(y_scale)

        def update(self, *_args) -> None:
            return None

        def reset(self, x=0.0, y=0.0) -> None:
            self.x = float(x)
            self.y = float(y)

    setattr(control_kinematics, "OmniKinematics", _OmniKinematics)
    setattr(control_kinematics, "Odometry", _Odometry)
    sys.modules["control.kinematics"] = control_kinematics

    filters_lowpass = ModuleType("filters.lowpass_filter")
    setattr(filters_lowpass, "LowPassFilter", lambda *args, **kwargs: None)
    sys.modules["filters.lowpass_filter"] = filters_lowpass

    filters_spike = ModuleType("filters.spike_filter")
    setattr(filters_spike, "SpikeMedianFilter", lambda *args, **kwargs: None)
    sys.modules["filters.spike_filter"] = filters_spike

    filters_diff = ModuleType("filters.diff_limit_filter")
    setattr(filters_diff, "DiffLimitFilter", lambda *args, **kwargs: None)
    sys.modules["filters.diff_limit_filter"] = filters_diff

    utils_quaternion = ModuleType("utils.quaternion")

    class _Quaternion:
        def update(self, *_args) -> None:
            return None

        def to_euler_yaw(self) -> float:
            return 0.0

    setattr(utils_quaternion, "Quaternion", _Quaternion)
    sys.modules["utils.quaternion"] = utils_quaternion

    utils_startup_log = ModuleType("utils.startup_log")
    setattr(utils_startup_log, "log", lambda *_args, **_kwargs: None)
    setattr(utils_startup_log, "log_exception", lambda *_args, **_kwargs: None)
    sys.modules["utils.startup_log"] = utils_startup_log

    hardware_uart_bus = ModuleType("hardware.uart_bus")
    setattr(hardware_uart_bus, "create_uart3", lambda: CaptureUart())
    setattr(hardware_uart_bus, "create_uart8", lambda: CaptureUart())
    setattr(hardware_uart_bus, "create_uart6", lambda: CaptureUart())
    sys.modules["hardware.uart_bus"] = hardware_uart_bus

    hardware_motors = ModuleType("hardware.motors")
    setattr(
        hardware_motors,
        "create_motors",
        lambda: {
            "m": DummyMotor(),
            "l": DummyMotor(),
            "r": DummyMotor(),
        },
    )
    sys.modules["hardware.motors"] = hardware_motors

    hardware_encoders = ModuleType("hardware.encoders")
    setattr(
        hardware_encoders,
        "create_encoders",
        lambda: {"m": None, "l": None, "r": None},
    )
    sys.modules["hardware.encoders"] = hardware_encoders

    hardware_imu = ModuleType("hardware.imu")

    class _Imu:
        def get(self):
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    setattr(hardware_imu, "create_imu", lambda: _Imu())
    sys.modules["hardware.imu"] = hardware_imu

    storage_param_manager = ModuleType("storage.param_manager")
    setattr(
        storage_param_manager,
        "load_ident_lookup",
        lambda _path: {
            "m": (0.0, 0.0),
            "l": (0.0, 0.0),
            "r": (0.0, 0.0),
        },
    )
    setattr(
        storage_param_manager,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )
    sys.modules["storage.param_manager"] = storage_param_manager

    config_package = sys.modules.get("config", ModuleType("config"))
    config_motion = ModuleType("config.motion")
    config_vision = ModuleType("config.vision")
    config_safety = ModuleType("config.safety")
    config_comm = ModuleType("config.comm")
    config_storage = ModuleType("config.storage")
    motion_values = {
        "TICK_MS": 5,
        "ROLE_STEP_MS": 100,
        "TRANSPORT_FORWARD_SPEED": 5.0,
        "TRANSPORT_CLEAR_STEP_DISTANCE_M": 0.12,
        "TRANSPORT_CLEAR_RETREAT_DISTANCE_M": 0.10,
        "TRANSPORT_CLEAR_RETREAT_MAX_SPEED": 3.0,
        "MOTION_STOP_SPEED_THRESHOLD": 0.5,
        "MOTION_STOP_CONFIRM_TICKS": 3,
        "POS_MAX_SPEED": 1.0,
        "POS_KP": 1.0,
        "MASTER_ODOMETRY_DISTANCE_SCALE": (1.25, 1.5),
        "ASSISTANT_ODOMETRY_DISTANCE_SCALE": (0.75, 0.5),
        "FIELD_SIZE_M": (3.2, 2.4),
        "MASTER_START_POSITION_M": (0.10, 0.0),
        "ASSISTANT_START_POSITION_M": (0.10, -0.50),
        "TRANSPORT_OBJECT_TARGET_EDGE": {-1: "bottom"},
        "POS_TOLERANCE": 0.01,
        "ANGLE_TOLERANCE": 1.0,
        "ACTIVE_WHEELS": ("m", "l", "r"),
        "GYRO_LPF_ALPHA": 0.5,
        "GYRO_SCALE": 1.0,
        "YAW_KP": 1.0,
        "YAW_KI": 0.0,
        "YAW_KD": 0.0,
        "YAW_I_MAX": 1.0,
        "AUTO_OMEGA_MAX": 15.0,
        "HEADING_TRANSITION_OMEGA_MAX": 30.0,
        "ORBIT_AUTO_OMEGA_MAX": 1.5,
        "ORBIT_ANGLE_CONFIRM_TICKS": 3,
        "HOLD_SPEED_EPS": 0.1,
        "MASTER_TURN_BACK_DELTA_DEG": 180,
        "MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG": 8.0,
        "MASTER_ORBIT_RADIUS_SCALE": 1.20,
        "ORBIT_POSITION_RADIUS_M": 0.13,
        "ASSISTANT_ORBIT_RADIUS_SCALE": 1.20,
        "ACTIVE_WHEELS": ("m", "l", "r"),
        "PID_MAP": {"m": (1.0, 0.0, 0.0), "l": (1.0, 0.0, 0.0), "r": (1.0, 0.0, 0.0)},
    }
    vision_values = {
        "RELIABLE_RESEND_INTERVAL_MS": 20,
        "MASTER_SEARCH_TASK_CONFIG_ID": 1,
        "MASTER_TRANSPORT_TASK_CONFIG_ID": 2,
        "MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID": 3,
        "MASTER_ORBIT_TASK_CONFIG_ID": 4,
        "MASTER_RETURN_GARAGE_LINE_TASK_CONFIG_ID": 5,
        "ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID": 5,
        "MASTER_RETURN_GARAGE_MARKER_TASK_CONFIG_ID": 6,
        "TRANSPORT_OBJECT_TOTAL_COUNT": 3,
        "ASSISTANT_APPROACH_OBJECT_CONFIG_ID": 1,
        "ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID": 2,
        "ASSISTANT_ORBIT_OBJECT_CONFIG_ID": 3,
        "ORBIT_VISION_CORRECTION_ENABLED": True,
        "ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE": 1.0,
        "ASSISTANT_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS": 20,
    }
    safety_values = {
        "POWER_MIN_VOLTAGE_V": 11.0,
        "MAX_DUTY": 1000,
        "TARGET_SPEED_MAX": 100.0,
        "V_CMD_MAX": 100.0,
    }
    comm_values = {
        "UART_BAUDRATE": 115200,
        "UART3_PORT_ID": 2,
        "UART6_PORT_ID": 5,
        "UART8_PORT_ID": 7,
        "TRANSPORT_FRAME_BODY_SIZE": 10,
        "TRANSPORT_FRAME_HEAD": 0xA5,
        "TRANSPORT_FRAME_SIZE": 15,
        "UDP_SEND_INTERVAL_MS": 20,
        "TCP_SEND_INTERVAL_MS": 150,
        "TRANSPORT_RX_READ_LIMIT": 32,
        "RELIABLE_RESEND_INTERVAL_MS": 20,
        "ASSISTANT_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS": 20,
        "SEQ_MIN": 0,
        "SEQ_MAX": 255,
        "SEQ_RING_SIZE": 256,
        "SEQ_HALF_RING": 128,
    }
    storage_values = {
        "IDENT_RESULTS_FILE": "ident.txt",
        "GYRO_OFFSET_FILE": "gyro.txt",
    }
    for key, value in motion_values.items():
        setattr(config_motion, key, value)
    for key, value in vision_values.items():
        setattr(config_vision, key, value)
    for key, value in safety_values.items():
        setattr(config_safety, key, value)
    for key, value in comm_values.items():
        setattr(config_comm, key, value)
    for key, value in storage_values.items():
        setattr(config_storage, key, value)
    setattr(config_package, "motion", config_motion)
    setattr(config_package, "vision", config_vision)
    setattr(config_package, "safety", config_safety)
    setattr(config_package, "comm", config_comm)
    setattr(config_package, "storage", config_storage)
    sys.modules["config"] = config_package
    sys.modules["config.motion"] = config_motion
    sys.modules["config.vision"] = config_vision
    sys.modules["config.safety"] = config_safety
    sys.modules["config.comm"] = config_comm
    sys.modules["config.storage"] = config_storage


def import_transport_car_module():
    """重新导入带测试桩的 `core.runtime` 模块."""
    install_transport_car_stubs()
    sys.modules.pop("core.runtime", None)
    return importlib.import_module("core.runtime")


def make_minimal_transport_car(**attrs):
    """构造未走初始化流程的最小 `TransportCar` 测试对象."""
    transport_car = import_transport_car_module()
    car = transport_car.TransportCar.__new__(transport_car.TransportCar)
    defaults = {
        "orbit_mode": False,
        "orbit_radius_scale": 1.0,
        "_orbit_pose_start": None,
        "_orbit_restore_integration": True,
        "_integrate_position": True,
    }
    defaults.update(attrs)
    for key, value in defaults.items():
        setattr(car, key, value)
    return transport_car, car
