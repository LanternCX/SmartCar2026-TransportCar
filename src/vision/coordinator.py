"""视觉观测缓存与状态推进协调器."""

from vision.state_machine import VisionMachineInputs
from vision.state_registry import vision_state_registry
from vision.transforms import resolve_relative_intent


class VisionRefreshResult:
    """封装一次视觉推进后的结果."""

    def __init__(self, step_result, resolved_target, released_heading_lock: bool):
        self.step_result = step_result
        self.resolved_target = resolved_target
        self.released_heading_lock = bool(released_heading_lock)


class VisionCoordinator:
    """拥有视觉协议缓存, 状态机推进和视觉快照构造."""

    def __init__(self, protocol, state_machine):
        self.protocol = protocol
        self.state_machine = state_machine
        self.step_result = None
        self.resolved_target = None

    def consume_uart_line(self, line: str, source: str, now_ms: int) -> bool:
        """尝试消费一行串口输入中的视觉观测."""
        parse_result = self.protocol.try_parse_observation(
            line, source=source, now_ms=now_ms
        )
        return bool(parse_result.consumed)

    def refresh(
        self,
        now_ms: int,
        heading_deg: float,
        odom_x: float,
        odom_y: float,
        command_lock: bool,
    ):
        """推进视觉状态机并刷新最新解析目标."""
        previous_target = self.resolved_target
        if command_lock:
            self.clear_runtime()
            return VisionRefreshResult(None, None, previous_target is not None)

        observation = self.protocol.get_observation(now_ms)
        inputs = VisionMachineInputs(
            observation=observation,
            heading_deg=heading_deg,
            odom_x=odom_x,
            odom_y=odom_y,
            now_ms=now_ms,
        )
        self.step_result = self.state_machine.step(inputs)
        self.resolved_target = resolve_relative_intent(
            self.step_result.intent,
            odom_x=odom_x,
            odom_y=odom_y,
            heading_deg=heading_deg,
        )
        return VisionRefreshResult(
            self.step_result,
            self.resolved_target,
            previous_target is not None and self.resolved_target is None,
        )

    def clear_runtime(self) -> None:
        """清空观测与状态机运行时状态."""
        self.protocol.clear()
        self.state_machine.reset()
        self.step_result = None
        self.resolved_target = None

    def get_observation(self, now_ms: int):
        """返回仍在有效期内的最新观测."""
        return self.protocol.get_observation(now_ms)

    def get_state_name(self) -> str:
        """返回当前视觉状态名."""
        state = getattr(self.state_machine, "state", None)
        if state is None:
            return "UNKNOWN"
        return vision_state_registry.get_state_name(int(state))

    def build_snapshot(self, now_ms: int):
        """构造视觉观测和解析目标快照."""
        observation = self.get_observation(now_ms)
        snapshot = {
            "state": self.get_state_name(),
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
        if observation is not None:
            snapshot["obs_age_ms"] = int(now_ms) - int(observation.timestamp_ms)
            snapshot["obs_left"] = float(observation.left)
            snapshot["obs_top"] = float(observation.top)
            snapshot["obs_right"] = float(observation.right)
            snapshot["obs_bottom"] = float(observation.bottom)
            snapshot["obs_center_x"] = float(observation.center_x)
            snapshot["obs_center_y"] = float(observation.center_y)
        if self.resolved_target is not None:
            snapshot["target_x"] = float(self.resolved_target.x)
            snapshot["target_y"] = float(self.resolved_target.y)
            snapshot["target_angle"] = float(self.resolved_target.angle_deg)
        return snapshot
