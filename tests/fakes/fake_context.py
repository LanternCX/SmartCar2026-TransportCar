"""命令处理器契约测试使用的假对象."""

from typing import Dict, List, Optional, cast

from diagnostics.manager import LogManager
from control.chassis_state import ChassisState
from services.runtime.diagnostics_facade import DiagnosticsFacade
from services.commanding.session import CommandSession


class FakeUART:
    """用于收集串口输出."""

    def __init__(self) -> None:
        self.messages: List[str] = []

    def write(self, text: str) -> None:
        self.messages.append(text)


class FakeOdometry:
    """带 reset 记录的里程计假对象."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.reset_called = False

    def reset(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.reset_called = True


class FakeYawPID:
    """带 reset 记录的偏航 PID 假对象."""

    def __init__(self) -> None:
        self.reset_called: bool = False

    def reset(self) -> None:
        self.reset_called = True


class FakeLPF:
    """带 reset 记录的低通滤波器假对象."""

    def __init__(self) -> None:
        self.last_reset_value: Optional[float] = None

    def reset(self, value: Optional[float] = None) -> None:
        self.last_reset_value = value


class FakeController:
    """轮控状态中的控制器假对象."""

    def __init__(self) -> None:
        self.reset_called: bool = False

    def reset(self) -> None:
        self.reset_called = True


class FakeQuaternion:
    """四元数容器假对象."""

    def __init__(self) -> None:
        self.w: float = 0.0
        self.x: float = 1.0
        self.y: float = 2.0
        self.z: float = 3.0


class FakeVisionProtocol:
    """视觉协议假对象."""

    def __init__(self) -> None:
        self.cleared: bool = False

    def clear(self) -> None:
        self.cleared = True


class FakeVisionStateMachine:
    """视觉状态机假对象."""

    def __init__(self) -> None:
        self.reset_called: bool = False

    def reset(self) -> None:
        self.reset_called = True


class FakeVisionCoordinator:
    """视觉协调器假对象."""

    def __init__(self) -> None:
        self.clear_runtime_called = False
        self.resolved_target = None

    def clear_runtime(self) -> None:
        self.clear_runtime_called = True

    def build_snapshot(self, _now_ms: int):
        return {
            "state": "UNKNOWN",
            "obs_age_ms": None,
            "obs_left": None,
            "obs_top": None,
            "obs_right": None,
            "obs_bottom": None,
            "obs_center_x": None,
            "obs_center_y": None,
            "target_x": None,
            "target_y": None,
            "target_angle": None,
        }


class FakeCommandContext:
    """命令与查询处理器使用的最小上下文假对象."""

    def __init__(self, reply_uart_name: str = "uart6") -> None:
        self.session = CommandSession()
        self.command_session = self.session
        self.uart3: FakeUART = FakeUART()
        self.uart6: FakeUART = FakeUART()
        self.reply_uart = cast(object, getattr(self, reply_uart_name))
        self.boot_time_ms: int = 0
        self.last_exception_text: str = "none"
        self.vision_coordinator: FakeVisionCoordinator = FakeVisionCoordinator()
        self.logger_manager: LogManager = LogManager()
        self.tick_count: int = 0
        self.last_loop_dt_us: int = 0
        self.max_loop_dt_us: int = 0
        self.loop_dt_total_us: int = 0
        self.loop_overrun_count: int = 0
        wheel_states = [
            {"name": "m", "controller": FakeController(), "duty": 9.0},
            {"name": "l", "controller": FakeController(), "duty": -3.0},
        ]
        self.chassis_state = ChassisState(
            odometry=FakeOdometry(),
            heading_est=0.0,
            heading_target=0.0,
            yaw_pid=FakeYawPID(),
            yaw_integral=0.0,
            q_est=FakeQuaternion(),
            last_yaw_rad=0.0,
            gyro_lpf=FakeLPF(),
            imu_data=[0.0] * 6,
            target_speeds={"m": 0.0, "l": 0.0, "r": 0.0},
            wheel_states=wheel_states,
        )

    def reply(self, text: str) -> None:
        """向当前 query 串口写回响应."""
        self.get_query_uart().write(text)

    def get_diagnostics_facade(self):
        """返回诊断 facade, 供 query handler 使用."""
        facade = getattr(self, "_diagnostics_facade", None)
        if facade is None:
            facade = DiagnosticsFacade(self)
            self._diagnostics_facade = facade
        return facade

    def now_ms(self) -> int:
        """返回用于 diagnostics facade 的当前毫秒数."""
        return 1000

    def reset_runtime(self) -> None:
        """按命令子系统语义复位运行时状态."""
        state = self.chassis_state
        odometry = state.odometry
        yaw_pid = state.yaw_pid
        q_est = state.q_est
        gyro_lpf = state.gyro_lpf
        if odometry is None or yaw_pid is None or q_est is None or gyro_lpf is None:
            raise AssertionError("fake context missing chassis state dependencies")
        odometry.reset()
        state.heading_est = 0.0
        state.heading_target = 0.0
        yaw_pid.reset()
        state.yaw_integral = 0.0
        q_est.w = 1.0
        q_est.x = 0.0
        q_est.y = 0.0
        q_est.z = 0.0
        state.last_yaw_rad = 0.0
        gyro_lpf.reset(0.0)
        for state in state.wheel_states:
            state["controller"].reset()
            state["duty"] = 0.0
        self.session.reset_runtime_state()
        self.vision_coordinator.clear_runtime()

    def get_query_uart(self):
        """返回当前查询响应应写入的串口."""
        return getattr(self, "reply_uart", self.uart6)
