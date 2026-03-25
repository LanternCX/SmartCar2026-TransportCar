"""@brief 搬运车视觉装配与目标仲裁 mixin.

@note
该模块负责把视觉协议, 双摄批次和状态机输入仲裁收口到 `TransportCar`
"""

import sys

from config.params import (
    VISION_ANGLE_DEADZONE_PX,
    VISION_ANGLE_KP,
    VISION_ANGLE_REENTRY_PX,
    VISION_CAMERA_POLL_ORDER,
    VISION_DIST_DEADZONE_PX,
    VISION_DIST_KP,
    VISION_DONE_HOLD_MS,
    VISION_DX_DEADZONE_PX,
    VISION_DX_KP,
    VISION_HEADING_TOLERANCE_DEG,
    VISION_MAX_DX_M,
    VISION_MAX_DY_M,
    VISION_MAX_D_ANGLE_DEG,
    VISION_PUSH_ANGLE_DEG,
    VISION_PUSH_DISTANCE_M,
    VISION_PUSH_DX_KP,
    VISION_PUSH_DY_M,
    VISION_ROLE_CAMERA_PRIORITIES,
    VISION_STABLE_FRAMES,
    VISION_TARGET_BOTTOM_PX,
    VISION_TARGET_CENTER_X_PX,
)
from services.car.bootstrap import DisabledVisionCoordinator, EMPTY_CAMERA_POLLS


class _LoggerContract:
    """@brief 静态分析用的最小 logger 契约."""

    def debug(self, _text):
        return None


class _UartContract:
    """@brief 静态分析用的最小串口契约."""

    def write(self, _text):
        return None


class _SessionContract:
    """@brief 静态分析用的最小命令会话契约."""

    def __init__(self):
        self.last_cmd = {}
        self.command_lock = False
        self.rear_only_mode = False


class _DisabledVisionService:
    """@brief 禁用视觉路径使用的轻量服务占位对象.

    @note
    该对象只保留既有兼容字段, 避免板端依赖 `types.SimpleNamespace`
    """

    __slots__ = ("enabled", "vision_runtime", "vision_coordinator")

    def __init__(self, coordinator):
        """@brief 构造禁用视觉占位对象.

        @param coordinator 禁用视觉协调器
        """
        self.enabled = False
        self.vision_runtime = None
        self.vision_coordinator = coordinator


class _VisionHost:
    """@brief 为静态分析声明 vision mixin 所需宿主接口.

    @note
    这些占位字段只为静态分析描述宿主承诺, 不拥有真实视觉状态
    """

    vehicle_role = "main"
    log_vision = _LoggerContract()
    uart6 = _UartContract()
    vision_processing_enabled = False
    dual_camera_polling_enabled = False
    command_session = _SessionContract()
    chassis_state = None
    vision_runtime = None
    vision_coordinator = None
    _active_vision_target_role = None
    _vision_debug_sink = None
    _vision_frame_query_cache = None

    def _now_ms(self):
        raise NotImplementedError


class VisionMixin(_VisionHost):
    """@brief 提供视觉装配与目标仲裁能力."""

    def _build_vision_coordinator(self):
        """@brief 按角色 profile 构造视觉协调器.

        @return 视觉协调器实例
        """
        if not self.vision_processing_enabled:
            coordinator = DisabledVisionCoordinator()
            self.vision_service = _DisabledVisionService(coordinator)
            self.vision_runtime = None
            return coordinator

        from services.runtime.vision_runtime_service import VisionRuntimeService

        service = VisionRuntimeService(
            vehicle_role=self.vehicle_role,
            build_disabled_coordinator=DisabledVisionCoordinator,
            build_state_config=self._build_vision_state_config,
            debug_sink=self._emit_vision_debug,
            frame_logger=self._log_vision_frame_boundary,
        )
        self.vision_service = service
        self.vision_runtime = service.vision_runtime
        return service

    def _build_vision_state_config(self):
        """@brief 构造视觉状态机配置对象.

        @return `VisionStateConfig`
        """
        from vision.state_machine import VisionStateConfig

        return VisionStateConfig(
            target_center_x_px=VISION_TARGET_CENTER_X_PX,
            target_bottom_px=VISION_TARGET_BOTTOM_PX,
            angle_kp=VISION_ANGLE_KP,
            dist_kp=VISION_DIST_KP,
            dx_kp=VISION_DX_KP,
            push_dx_kp=VISION_PUSH_DX_KP,
            push_dy_m=VISION_PUSH_DY_M,
            push_distance_m=VISION_PUSH_DISTANCE_M,
            push_angle_deg=VISION_PUSH_ANGLE_DEG,
            angle_deadzone_px=VISION_ANGLE_DEADZONE_PX,
            angle_reentry_px=VISION_ANGLE_REENTRY_PX,
            dist_deadzone_px=VISION_DIST_DEADZONE_PX,
            dx_deadzone_px=VISION_DX_DEADZONE_PX,
            heading_tolerance_deg=VISION_HEADING_TOLERANCE_DEG,
            stable_frames=VISION_STABLE_FRAMES,
            max_dx_m=VISION_MAX_DX_M,
            max_dy_m=VISION_MAX_DY_M,
            max_d_angle_deg=VISION_MAX_D_ANGLE_DEG,
            done_hold_ms=VISION_DONE_HOLD_MS,
        )

    def _emit_vision_debug(self, event) -> None:
        """@brief 输出单条视觉调试事件.

        @param event 调试事件对象
        """

        # debug sink 首次访问时再构造, 避免在无视觉调试场景下引入多余闭包对象
        sink = getattr(self, "_vision_debug_sink", None)
        if sink is None:
            module = getattr(self.__class__, "_public_module_ref", None)
            if module is None:
                module = sys.modules.get(self.__class__.__module__)
            from vision.debug import build_logger_debug_sink

            sink_builder = getattr(
                module, "build_logger_debug_sink", build_logger_debug_sink
            )
            sink = sink_builder(self.log_vision)
            self._vision_debug_sink = sink
        sink(event)

    def _get_vision_camera_poll_order(self):
        """@brief 返回双摄轮询顺序."""
        module = getattr(self.__class__, "_public_module_ref", None)
        if module is not None:
            poll_order = getattr(module, "VISION_CAMERA_POLL_ORDER", None)
            if poll_order is not None:
                return poll_order
        return VISION_CAMERA_POLL_ORDER

    def _get_vision_role_camera_priorities(self):
        """@brief 返回角色到相机优先级映射."""
        return VISION_ROLE_CAMERA_PRIORITIES

    def _get_cached_vision_frame_query(self, camera_id: str) -> str:
        """@brief 返回指定相机的缓存查询串.

        @param camera_id 相机标识
        @return 复用查询串
        """
        cache = getattr(self, "_vision_frame_query_cache", None)
        if cache is None:
            cache = {}
            self._vision_frame_query_cache = cache
        query = cache.get(camera_id)
        if query is None:
            from vision.protocol import VisionProtocol

            query = VisionProtocol.build_frame_query(camera_id) + "\r\n"
            cache[camera_id] = query
        return query

    def _log_vision_poll(self, camera_id: str) -> None:
        """@brief 记录一次视觉轮询边界."""
        self.log_vision.debug("POLL camera=%s" % str(camera_id))

    def _log_vision_frame_boundary(
        self, camera_id: str, frame_id: str, detections_count: int
    ):
        """@brief 记录单帧视觉边界和检测数量."""
        self.log_vision.debug(
            "FRAME camera=%s frame=%s end detections=%d"
            % (str(camera_id), str(frame_id), int(detections_count))
        )

    def _poll_vision_cameras(self, poll_budget=None):
        """@brief 轮询视觉相机并返回本拍查询顺序.

        @param poll_budget 可选轮询预算
        @return 本拍已轮询相机列表或空元组
        """

        # 辅车 profile 不应主动触发视觉查询, 直接返回空轮询结果
        if not self.dual_camera_polling_enabled:
            return EMPTY_CAMERA_POLLS
        self._ensure_vision_coordinator()
        poll_order = self._get_vision_camera_poll_order()
        if poll_budget is None:
            for camera_id in poll_order:
                self._log_vision_poll(camera_id)
                self.uart6.write(self._get_cached_vision_frame_query(camera_id))
            return poll_order
        budget = int(poll_budget)
        if budget <= 0:
            return EMPTY_CAMERA_POLLS
        polled = []
        for camera_id in poll_order[:budget]:
            self._log_vision_poll(camera_id)
            self.uart6.write(self._get_cached_vision_frame_query(camera_id))
            polled.append(camera_id)
        return polled

    def _get_vision_resolved_target(self):
        """@brief 返回当前解析完成的视觉目标.

        @return 当前 `resolved_target` 或 `None`
        """

        # 优先读取 runtime owner, 再回退到 coordinator 兼容旧测试构造方式
        runtime = getattr(self, "vision_runtime", None)
        if runtime is None:
            runtime = getattr(
                getattr(self, "vision_coordinator", None), "runtime", None
            )
        if runtime is not None:
            current = getattr(runtime, "resolved_target", None)
            if current is not None:
                return current
        coordinator = getattr(self, "vision_coordinator", None)
        if coordinator is None:
            return None
        return getattr(coordinator, "resolved_target", None)

    def _select_vision_state_machine_input(self, now_ms: int):
        """@brief 从双摄批次中挑选当前状态机输入.

        @param now_ms 当前毫秒时间
        @return 状态机输入对象
        """
        from vision.transforms import select_state_machine_input

        # 双摄批次可能出现只有部分相机更新的情况, 这里先探测是否存在完整 frame batch
        coordinator = self._ensure_vision_coordinator()
        runtime = getattr(self, "vision_runtime", None) or getattr(
            coordinator, "runtime", None
        )
        has_frame_batches = False
        if runtime is not None:
            for camera_id in self._get_vision_camera_poll_order():
                frame = None
                if hasattr(coordinator, "get_frame"):
                    frame = coordinator.get_frame(camera_id, now_ms)
                elif hasattr(runtime, "get_slot"):
                    frame = getattr(runtime.get_slot(camera_id), "frame", None)
                if frame is not None:
                    has_frame_batches = True
                    break
        selected = select_state_machine_input(
            runtime=runtime,
            active_target_role=getattr(self, "_active_vision_target_role", None),
            role_camera_priorities=self._get_vision_role_camera_priorities(),
        )
        if (
            not has_frame_batches
            and runtime is not None
            and selected.observation is None
        ):
            selected.observation = getattr(runtime, "latest_observation", None)
        if not has_frame_batches and runtime is None and selected.observation is None:
            if hasattr(coordinator, "get_observation"):
                selected.observation = coordinator.get_observation(now_ms)
        if selected.target_role is not None:
            self._active_vision_target_role = selected.target_role
        return selected

    def _refresh_vision_target(self, now_ms=None):
        """@brief 推进视觉状态机并刷新当前目标.

        @param now_ms 当前毫秒时间, 为空时自动取当前时间
        """

        # 禁用视觉 profile 直接短路, 避免无意义轮询和状态机推进
        if not self.vision_processing_enabled:
            return
        if now_ms is None:
            now_ms = self._now_ms()
        self._poll_vision_cameras()
        chassis_state = self.chassis_state
        if chassis_state is None:
            return
        odometry = chassis_state.odometry
        heading_est = float(chassis_state.heading_est or 0.0)
        selected = self._select_vision_state_machine_input(now_ms)
        result = self._ensure_vision_coordinator().refresh(
            now_ms=now_ms,
            heading_deg=heading_est,
            odom_x=float(odometry.x if odometry is not None else 0.0),
            odom_y=float(odometry.y if odometry is not None else 0.0),
            command_lock=self.command_session.command_lock,
            selected_input=selected,
        )
        if bool(result.released_heading_lock):
            chassis_state.heading_target = heading_est
            yaw_pid = chassis_state.yaw_pid
            if yaw_pid is not None:
                yaw_pid.reset()
            chassis_state.yaw_integral = 0.0
        if (
            result.resolved_target is None
            and getattr(selected, "target_role", None) is None
        ):
            self._active_vision_target_role = None

    def _get_active_position_targets(self):
        """@brief 返回当前激活控制源的位置目标.

        @return `(x, y)` 目标二元组
        """
        current = self._get_vision_resolved_target()
        if current is not None:
            return current.x, current.y
        last_cmd = self.command_session.last_cmd
        return last_cmd.get("x"), last_cmd.get("y")

    def _get_active_angle_command(self):
        """@brief 返回当前激活控制源的角度目标.

        @return 当前角度目标或 `None`
        """
        current = self._get_vision_resolved_target()
        if current is not None:
            return current.angle_deg
        return self.command_session.last_cmd.get("angle")

    def _compute_angle_error_deg(
        self, target_angle: float, current_angle: float
    ) -> float:
        """@brief 计算最短路径角差.

        @param target_angle 目标角度
        @param current_angle 当前角度
        @return 归一化后的角差
        """
        from vision.transforms import normalize_angle

        return normalize_angle(float(target_angle) - float(current_angle))

    def _resolve_continuous_heading_target(
        self, target_angle: float, current_angle: float
    ) -> float:
        """@brief 将目标角映射到当前连续航向附近.

        @param target_angle 目标角度
        @param current_angle 当前角度
        @return 连续航向域内的目标角
        """
        return float(current_angle) + self._compute_angle_error_deg(
            target_angle, current_angle
        )

    def _get_active_rear_only_mode(self):
        """@brief 返回当前激活控制源的后轮模式."""
        current = self._get_vision_resolved_target()
        if current is not None:
            return current.rear_only_mode
        return self.command_session.rear_only_mode

    def _get_vision_state_name(self):
        """@brief 返回当前视觉状态机状态名."""
        coordinator = getattr(self, "vision_coordinator", None)
        if coordinator is None:
            return "UNKNOWN"
        if hasattr(coordinator, "get_state_name"):
            return coordinator.get_state_name()
        from vision.state_registry import vision_state_registry

        state = getattr(getattr(coordinator, "state_machine", None), "state", None)
        if state is None:
            return "UNKNOWN"
        return vision_state_registry.get_state_name(int(state))

    def _ensure_vision_coordinator(self):
        """@brief 返回视觉协调器, 缺失时按需懒构造.

        @return 视觉协调器对象
        """

        # coordinator 被替换后, 这里还要把最新 runtime 指针回写到宿主, 避免 owner 漂移
        coordinator = getattr(self, "vision_coordinator", None)
        if coordinator is None:
            coordinator = self._build_vision_coordinator()
            self.vision_coordinator = coordinator
        elif hasattr(coordinator, "frame_logger"):
            coordinator.frame_logger = self._log_vision_frame_boundary
        runtime = getattr(coordinator, "runtime", None)
        if runtime is not None:
            self.vision_runtime = runtime
        return coordinator
