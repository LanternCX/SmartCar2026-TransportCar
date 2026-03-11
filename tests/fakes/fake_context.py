"""命令处理器契约测试使用的假对象."""

from typing import Dict, List, Optional

from diagnostics.manager import LogManager, QueryUARTLike, SnapshotBuilder


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


def _empty_snapshot() -> Dict[str, object]:
    """返回空诊断快照."""
    return {}


class FakeCommandContext:
    """命令与查询处理器使用的最小上下文假对象."""

    def __init__(self) -> None:
        self.command_lock: bool = False
        self.last_cmd: Dict[str, float] = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self._pending_dx: Optional[float] = None
        self._pending_dy: Optional[float] = None
        self._pending_d_angle: Optional[float] = None
        self._rear_mode_changed: bool = False
        self.rear_only_mode: bool = False
        self.uart3: FakeUART = FakeUART()
        self.uart6: FakeUART = FakeUART()
        self.odometry: FakeOdometry = FakeOdometry()
        self.heading_est: float = 0.0
        self.heading_target: float = 0.0
        self.yaw_pid: FakeYawPID = FakeYawPID()
        self.yaw_integral: float = 0.0
        self.q_est: FakeQuaternion = FakeQuaternion()
        self.last_yaw_rad: float = 0.0
        self.gyro_lpf: FakeLPF = FakeLPF()
        self.vision_protocol: FakeVisionProtocol = FakeVisionProtocol()
        self.vision_state_machine: FakeVisionStateMachine = FakeVisionStateMachine()
        self._vision_step_result: object = object()
        self._vision_resolved_target: object = object()
        self._query_response_uart: QueryUARTLike = self.uart6
        self.logger_manager: LogManager = LogManager()
        self.wheel_states = [
            {"controller": FakeController(), "duty": 9.0},
            {"controller": FakeController(), "duty": -3.0},
        ]
        self.build_health_snapshot: SnapshotBuilder = _empty_snapshot
        self.build_tick_snapshot: SnapshotBuilder = _empty_snapshot
        self.build_imu_snapshot: SnapshotBuilder = _empty_snapshot
        self.build_encoder_snapshot: SnapshotBuilder = _empty_snapshot
        self.build_motor_snapshot: SnapshotBuilder = _empty_snapshot
        self.build_vision_snapshot: SnapshotBuilder = _empty_snapshot

    def get_query_uart(self) -> QueryUARTLike:
        """返回当前查询响应应写入的串口."""
        return getattr(self, "_query_response_uart", self.uart6)
