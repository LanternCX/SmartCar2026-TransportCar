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
        "config.params",
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
        lambda *args, **kwargs: {
            "name": args[0],
            "motor": args[2],
            "controller": kwargs["pid_controller"],
            "filtered_speed": 0.0,
        },
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
        def __init__(self) -> None:
            self.x = 0.0
            self.y = 0.0

        def update(self, *_args) -> None:
            return None

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
    setattr(utils_startup_log, "startup_log", lambda *_args, **_kwargs: None)
    sys.modules["utils.startup_log"] = utils_startup_log

    hardware_uart_bus = ModuleType("hardware.uart_bus")
    setattr(hardware_uart_bus, "create_uart3", lambda: CaptureUart())
    setattr(hardware_uart_bus, "create_uart8", lambda: CaptureUart())
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

    config_params = ModuleType("config.params")
    param_values = {
        "TICK_MS": 5,
        "MAX_DUTY": 1000,
        "TARGET_SPEED_MAX": 100.0,
        "V_CMD_MAX": 100.0,
        "POS_MAX_SPEED": 1.0,
        "POS_KP": 1.0,
        "POS_TOLERANCE": 0.01,
        "ANGLE_TOLERANCE": 1.0,
        "ACTIVE_WHEELS": ("m", "l", "r"),
        "GYRO_LPF_ALPHA": 0.5,
        "GYRO_SCALE": 1.0,
        "YAW_KP": 1.0,
        "YAW_KI": 0.0,
        "YAW_KD": 0.0,
        "YAW_I_MAX": 1.0,
        "AUTO_OMEGA_MAX": 10.0,
        "HOLD_SPEED_EPS": 0.1,
        "IDENT_RESULTS_FILE": "ident.txt",
        "GYRO_OFFSET_FILE": "gyro.txt",
        "PID_MAP": {"m": (1.0, 0.0, 0.0), "l": (1.0, 0.0, 0.0), "r": (1.0, 0.0, 0.0)},
        "VISION_OBSERVATION_TIMEOUT_MS": 100,
        "VISION_TARGET_X_PX": 0.0,
        "VISION_TARGET_Y_PX": 0.0,
        "VISION_ANGLE_KP": 0.0,
        "VISION_DIST_KP": 0.0,
        "VISION_DX_KP": 0.0,
        "VISION_PUSH_DX_KP": 0.0,
        "VISION_PUSH_DY_M": 0.0,
        "VISION_PUSH_DISTANCE_M": 0.0,
        "VISION_PUSH_ANGLE_DEG": 0.0,
        "VISION_ANGLE_DEADZONE_PX": 0.0,
        "VISION_ANGLE_REENTRY_PX": 0.0,
        "VISION_DIST_DEADZONE_PX": 0.0,
        "VISION_DX_DEADZONE_PX": 0.0,
        "VISION_HEADING_TOLERANCE_DEG": 0.0,
        "VISION_STABLE_FRAMES": 1,
        "VISION_MAX_DX_M": 0.0,
        "VISION_MAX_DY_M": 0.0,
        "VISION_MAX_D_ANGLE_DEG": 0.0,
        "VISION_DONE_HOLD_MS": 0,
    }
    for key, value in param_values.items():
        setattr(config_params, key, value)
    sys.modules["config.params"] = config_params


def import_transport_car_module():
    """重新导入带测试桩的 `core.runtime` 模块."""
    install_transport_car_stubs()
    sys.modules.pop("core.runtime", None)
    return importlib.import_module("core.runtime")


def make_minimal_transport_car(**attrs):
    """构造未走初始化流程的最小 `TransportCar` 测试对象."""
    transport_car = import_transport_car_module()
    car = transport_car.TransportCar.__new__(transport_car.TransportCar)
    for key, value in attrs.items():
        setattr(car, key, value)
    return transport_car, car
