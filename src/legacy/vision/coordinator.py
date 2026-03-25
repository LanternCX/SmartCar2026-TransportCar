"""视觉观测缓存与状态推进协调器."""

from vision.runtime import VisionRuntime
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

    def __init__(self, protocol, state_machine, frame_logger=None, runtime=None):
        if runtime is None:
            runtime = getattr(protocol, "runtime", None)
        if runtime is None:
            runtime = VisionRuntime(timeout_ms=getattr(protocol, "timeout_ms", 0))
        self.runtime = runtime
        self.protocol = protocol
        self.state_machine = state_machine
        self.frame_logger = frame_logger
        self.step_result = None

    @property
    def resolved_target(self):
        """返回 runtime owner 中保存的最新解析目标."""
        return self.runtime.resolved_target

    @resolved_target.setter
    def resolved_target(self, value) -> None:
        self.runtime.resolved_target = value

    def consume_uart_line(self, line: str, source: str, now_ms: int) -> bool:
        """尝试消费一行串口输入中的视觉观测."""
        previous_frame = self.runtime.latest_frame
        parse_result = self.protocol.try_parse_observation(
            line, source=source, now_ms=now_ms
        )
        latest_frame = self.runtime.latest_frame
        if latest_frame is not None and latest_frame is not previous_frame:
            if self.frame_logger is not None:
                self.frame_logger(
                    camera_id=str(latest_frame.camera_id),
                    frame_id=str(latest_frame.frame_id),
                    detections_count=len(latest_frame.detections),
                )
        return bool(parse_result.consumed)

    def refresh(
        self,
        now_ms: int,
        heading_deg: float,
        odom_x: float,
        odom_y: float,
        command_lock: bool,
        selected_input=None,
    ):
        """推进视觉状态机并刷新最新解析目标."""
        previous_target = self.resolved_target
        if command_lock:
            self.clear_runtime()
            return VisionRefreshResult(None, None, previous_target is not None)

        observation = self.protocol.get_observation(now_ms)
        target_role = None
        obstacle_summary = None
        if selected_input is not None:
            observation = selected_input.observation
            target_role = selected_input.target_role
            obstacle_summary = selected_input.obstacle_summary
        self.runtime.selected_input = selected_input
        if selected_input is None and observation is not None:
            self.runtime.selected_input = None
        inputs = VisionMachineInputs(
            observation=observation,
            heading_deg=heading_deg,
            odom_x=odom_x,
            odom_y=odom_y,
            now_ms=now_ms,
            target_role=target_role,
            obstacle_summary=obstacle_summary,
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
        self.runtime.selected_input = None
        self.runtime.snapshot_buffer = None

    def get_observation(self, now_ms: int):
        """返回仍在有效期内的最新观测."""
        return self.protocol.get_observation(now_ms)

    def get_frame(self, camera_id: str, now_ms: int):
        """返回指定相机仍在有效期内的最新检测批次."""
        frame = getattr(self.runtime.get_slot(camera_id), "frame", None)
        if frame is None:
            return None
        if int(now_ms) - int(frame.timestamp_ms) > int(self.protocol.timeout_ms):
            slot = self.runtime.get_slot(camera_id)
            slot.frame = None
            slot.timestamp_ms = None
            return None
        return frame

    def get_state_name(self) -> str:
        """返回当前视觉状态名."""
        state = getattr(self.state_machine, "state", None)
        if state is None:
            return "UNKNOWN"
        return vision_state_registry.get_state_name(int(state))

    def build_snapshot(self, now_ms: int):
        """构造视觉观测和解析目标快照."""
        selected_input = self.runtime.selected_input
        observation = None
        if selected_input is not None:
            observation = getattr(selected_input, "observation", None)
        if observation is None:
            observation = self.runtime.latest_observation
        snapshot = self.runtime.snapshot_buffer
        if not isinstance(snapshot, dict):
            snapshot = {
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
            setattr(self.runtime, "snapshot_buffer", snapshot)
        snapshot["state"] = self.get_state_name()
        snapshot["obs_age_ms"] = None
        snapshot["obs_left"] = None
        snapshot["obs_top"] = None
        snapshot["obs_right"] = None
        snapshot["obs_bottom"] = None
        snapshot["obs_center_x"] = None
        snapshot["obs_center_y"] = None
        snapshot["target_x"] = None
        snapshot["target_y"] = None
        snapshot["target_angle"] = None
        if observation is not None:
            snapshot["obs_age_ms"] = int(now_ms) - int(observation.timestamp_ms)
            snapshot["obs_left"] = float(observation.left)
            snapshot["obs_top"] = float(observation.top)
            snapshot["obs_right"] = float(observation.right)
            snapshot["obs_bottom"] = float(observation.bottom)
            snapshot["obs_center_x"] = float(observation.center_x)
            snapshot["obs_center_y"] = float(observation.center_y)
        resolved_target = self.runtime.resolved_target
        if resolved_target is not None:
            target_x = getattr(resolved_target, "x", None)
            target_y = getattr(resolved_target, "y", None)
            target_angle = getattr(resolved_target, "angle_deg", None)
            if target_x is not None:
                snapshot["target_x"] = float(target_x)
            if target_y is not None:
                snapshot["target_y"] = float(target_y)
            if target_angle is not None:
                snapshot["target_angle"] = float(target_angle)
        return snapshot
