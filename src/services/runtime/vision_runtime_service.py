"""@brief 按角色装配视觉运行时 owner."""

from config.params import VISION_OBSERVATION_TIMEOUT_MS


class VisionRuntimeService:
    """@brief 持有按角色启用的视觉运行时与协调器.

    @note
    主车路径先只构造轻量 runtime, protocol/state_machine/coordinator
    延迟到首次真正访问协调器接口时再创建, 以降低首次视觉激活峰值
    """

    def __init__(
        self,
        vehicle_role,
        build_disabled_coordinator=None,
        build_state_config=None,
        debug_sink=None,
        frame_logger=None,
        build_runtime=None,
        build_coordinator=None,
    ) -> None:
        self.vehicle_role = str(vehicle_role)
        self.enabled = self.vehicle_role == "main"
        self._build_state_config = build_state_config
        self._debug_sink = debug_sink
        self._frame_logger = frame_logger
        self._build_coordinator = build_coordinator
        if not self.enabled:
            disabled_builder = build_disabled_coordinator
            if disabled_builder is None:
                raise ValueError(
                    "build_disabled_coordinator is required for disabled role"
                )
            self.vision_runtime = None
            self.vision_coordinator = disabled_builder()
            return

        runtime_builder = build_runtime or self._build_default_runtime
        self.vision_runtime = runtime_builder(VISION_OBSERVATION_TIMEOUT_MS)

        if self._build_state_config is None and self._build_coordinator is None:
            raise ValueError("build_state_config is required for main role")

    def _build_default_runtime(self, timeout_ms):
        """@brief 构造默认视觉 runtime."""
        from vision.runtime import VisionRuntime

        return VisionRuntime(timeout_ms)

    def _ensure_vision_coordinator(self):
        """@brief 按需构造主车视觉协调器."""
        coordinator = getattr(self, "vision_coordinator", None)
        if coordinator is not None:
            return coordinator
        builder = self._build_coordinator
        if builder is not None:
            coordinator = builder(self.vision_runtime)
        else:
            state_config_builder = self._build_state_config
            if state_config_builder is None:
                raise ValueError("build_state_config is required for main role")
            from vision.coordinator import VisionCoordinator
            from vision.protocol import VisionProtocol
            from vision.state_machine import VisionStateMachine

            protocol = VisionProtocol(self.vision_runtime)
            state_machine = VisionStateMachine(
                state_config_builder(), debug_sink=self._debug_sink
            )
            coordinator = VisionCoordinator(
                runtime=self.vision_runtime,
                protocol=protocol,
                state_machine=state_machine,
                frame_logger=self._frame_logger,
            )
        self.vision_coordinator = coordinator
        return coordinator

    @property
    def runtime(self):
        """@brief 返回共享视觉 runtime."""
        return self.vision_runtime

    @property
    def protocol(self):
        """@brief 返回视觉协议实例."""
        return self._ensure_vision_coordinator().protocol

    @property
    def state_machine(self):
        """@brief 返回视觉状态机实例."""
        return self._ensure_vision_coordinator().state_machine

    @property
    def resolved_target(self):
        """@brief 返回当前解析目标."""
        return self._ensure_vision_coordinator().resolved_target

    @resolved_target.setter
    def resolved_target(self, value) -> None:
        self._ensure_vision_coordinator().resolved_target = value

    @property
    def step_result(self):
        """@brief 返回最近一步状态机结果."""
        return self._ensure_vision_coordinator().step_result

    @step_result.setter
    def step_result(self, value) -> None:
        self._ensure_vision_coordinator().step_result = value

    def consume_uart_line(self, line: str, source: str, now_ms: int) -> bool:
        """@brief 转发 UART 行到懒构造协调器."""
        return self._ensure_vision_coordinator().consume_uart_line(line, source, now_ms)

    def refresh(
        self,
        now_ms: int,
        heading_deg: float,
        odom_x: float,
        odom_y: float,
        command_lock: bool,
        selected_input=None,
    ):
        """@brief 推进视觉状态机并返回最新结果."""
        return self._ensure_vision_coordinator().refresh(
            now_ms=now_ms,
            heading_deg=heading_deg,
            odom_x=odom_x,
            odom_y=odom_y,
            command_lock=command_lock,
            selected_input=selected_input,
        )

    def clear_runtime(self) -> None:
        """@brief 清理视觉 runtime 缓存."""
        self._ensure_vision_coordinator().clear_runtime()

    def get_observation(self, now_ms: int):
        """@brief 返回当前观测."""
        return self._ensure_vision_coordinator().get_observation(now_ms)

    def get_state_name(self) -> str:
        """@brief 返回当前视觉状态名."""
        return self._ensure_vision_coordinator().get_state_name()

    def build_snapshot(self, now_ms: int):
        """@brief 返回视觉快照."""
        return self._ensure_vision_coordinator().build_snapshot(now_ms)

    def get_frame(self, camera_id: str, now_ms: int):
        """@brief 返回指定相机帧."""
        return self._ensure_vision_coordinator().get_frame(camera_id, now_ms)
