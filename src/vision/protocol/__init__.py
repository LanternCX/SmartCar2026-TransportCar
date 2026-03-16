"""@brief 视觉协议公开入口与运行时 owner 写入."""

from vision.protocol.batch import (
    clear_invalid_batch,
    clear_pending_frame,
    clear_runtime,
    commit_frame,
    commit_pending_frame,
    has_invalid_batch,
    is_invalid_batch,
    set_invalid_batch,
)
from vision.protocol.parse import (
    is_reserved_payload,
    parse_line_items,
    try_parse_observation,
)
from vision.protocol.query import (
    build_frame_query,
    is_query_for_camera,
    is_reserved_query,
    normalize_camera_id,
)
from vision.runtime import VisionRuntime


class VisionFrame:
    """@brief 单次查询对应的一帧检测集合."""

    def __init__(self, camera_id: str, frame_id: str, detections, timestamp_ms: int):
        self.camera_id = str(camera_id)
        self.frame_id = str(frame_id)
        self.detections = list(detections)
        self.timestamp_ms = int(timestamp_ms)


class VisionObservation:
    """@brief 单帧视觉识别框观测."""

    def __init__(
        self,
        left,
        top,
        right,
        bottom,
        timestamp_ms,
        camera_id=None,
        frame_id=None,
        category=None,
    ):
        self.left = float(left)
        self.top = float(top)
        self.right = float(right)
        self.bottom = float(bottom)
        self.center_x = (self.left + self.right) / 2.0
        self.center_y = (self.top + self.bottom) / 2.0
        self.width = self.right - self.left
        self.height = self.bottom - self.top
        self.timestamp_ms = int(timestamp_ms)
        self.camera_id = None if camera_id is None else str(camera_id)
        self.frame_id = None if frame_id is None else str(frame_id)
        self.category = None if category is None else str(category)


class VisionParseResult:
    """@brief 单行视觉协议解析结果."""

    def __init__(self, consumed: bool, observation):
        self.consumed = bool(consumed)
        self.observation = observation


class VisionProtocol:
    """@brief 解析 UART6 识别框视觉包并写入运行时 owner."""

    _BBOX_KEYS = ("left", "top", "right", "bottom")
    _FRAME_META_KEYS = ("camera_id", "frame_id", "category", "frame_end")
    _VISUAL_KEYS = _BBOX_KEYS + ("x", "y") + _FRAME_META_KEYS
    __slots__ = (
        "runtime",
        "timeout_ms",
        "_pending_camera_id",
        "_pending_frame_id",
        "_invalid_pending_camera_id",
        "_invalid_pending_frame_id",
        "_invalid_jumped_camera_id",
        "_invalid_jumped_frame_id",
    )
    _frame_type = VisionFrame
    _observation_type = VisionObservation
    _parse_result_type = VisionParseResult

    def __init__(self, runtime_or_timeout_ms=None, timeout_ms=None):
        if isinstance(runtime_or_timeout_ms, VisionRuntime):
            self.runtime = runtime_or_timeout_ms
            self.timeout_ms = int(self.runtime.timeout_ms)
        else:
            if timeout_ms is None:
                timeout_ms = runtime_or_timeout_ms
            if timeout_ms is None:
                timeout_ms = 0
            self.timeout_ms = int(timeout_ms)
            self.runtime = VisionRuntime(timeout_ms=self.timeout_ms)
        self._pending_camera_id = None
        self._pending_frame_id = None
        self._invalid_pending_camera_id = None
        self._invalid_pending_frame_id = None
        self._invalid_jumped_camera_id = None
        self._invalid_jumped_frame_id = None

    def _slot_for_camera(self, camera_id: str):
        return self.runtime.get_slot(camera_id)

    def _get_pending_detections(self):
        camera_id = self._pending_camera_id
        if camera_id is None:
            return None
        return self._slot_for_camera(camera_id).pending_items

    def _ensure_pending_detections(self):
        camera_id = self._pending_camera_id
        if camera_id is None:
            return []
        slot = self._slot_for_camera(camera_id)
        if slot.pending_items is None:
            slot.pending_items = []
        return slot.pending_items

    _normalize_camera_id = staticmethod(normalize_camera_id)
    build_frame_query = staticmethod(build_frame_query)
    is_query_for_camera = staticmethod(is_query_for_camera)
    is_reserved_query = staticmethod(is_reserved_query)
    _parse_line_items = staticmethod(parse_line_items)
    _clear_pending_frame = clear_pending_frame
    _set_invalid_batch = set_invalid_batch
    _clear_invalid_batch = clear_invalid_batch
    _has_invalid_batch = has_invalid_batch
    _is_invalid_batch = is_invalid_batch
    _commit_frame = commit_frame
    _commit_pending_frame = commit_pending_frame
    is_reserved_payload = classmethod(is_reserved_payload)
    try_parse_observation = try_parse_observation

    def get_frame(self, now_ms: int):
        latest_frame = self.runtime.latest_frame
        if latest_frame is None:
            return None
        if int(now_ms) - latest_frame.timestamp_ms > self.timeout_ms:
            slot = self._slot_for_camera(latest_frame.camera_id)
            slot.frame = None
            slot.timestamp_ms = None
            self.runtime.latest_frame = None
            if (
                self.runtime.latest_observation is not None
                and getattr(self.runtime.latest_observation, "frame_id", None)
                is not None
            ):
                self.runtime.latest_observation = None
            return None
        return latest_frame

    def get_observation(self, now_ms: int):
        latest_frame = self.get_frame(now_ms)
        latest_observation = self.runtime.latest_observation
        if latest_frame is None and latest_observation is not None:
            if getattr(latest_observation, "frame_id", None) is not None:
                return None
        if latest_observation is None:
            return None
        if int(now_ms) - latest_observation.timestamp_ms > self.timeout_ms:
            self.runtime.latest_observation = None
            return None
        return latest_observation

    def shift_latest_timestamp(self, delta_ms: int) -> None:
        latest_observation = self.runtime.latest_observation
        latest_frame = self.runtime.latest_frame
        if latest_observation is None and latest_frame is None:
            return
        if latest_observation is not None:
            latest_observation.timestamp_ms += int(delta_ms)
        if latest_frame is not None:
            latest_frame.timestamp_ms += int(delta_ms)

    def clear(self) -> None:
        clear_runtime(self)


__all__ = (
    "VisionFrame",
    "VisionObservation",
    "VisionParseResult",
    "VisionProtocol",
)
