"""视觉协议解析与最新观测缓存."""


class VisionFrame:
    """单次查询对应的一帧检测集合."""

    def __init__(self, camera_id: str, frame_id: str, detections, timestamp_ms: int):
        """保存相机标识, 帧标识, 检测列表与时间戳."""
        self.camera_id = str(camera_id)
        self.frame_id = str(frame_id)
        self.detections = list(detections)
        self.timestamp_ms = int(timestamp_ms)


class VisionObservation:
    """单帧视觉识别框观测."""

    def __init__(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        timestamp_ms: int,
        camera_id=None,
        frame_id=None,
        category=None,
    ):
        """保存视觉框、派生几何量与时间戳."""
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
    """单行视觉协议解析结果."""

    def __init__(self, consumed: bool, observation):
        """保存本行是否被视觉协议消费及观测对象."""
        self.consumed = bool(consumed)
        self.observation = observation


class VisionProtocol:
    """解析 UART6 识别框视觉包并维护最新观测.

    约定: OpenArt 侧在发送前已经对传感器画面启用了翻转, 因此这里接收的
    `left,top,right,bottom` 已经是翻转后画面的像素坐标, 主控侧不再重复做
    坐标翻转.
    """

    _BBOX_KEYS = ("left", "top", "right", "bottom")
    _FRAME_META_KEYS = ("camera_id", "frame_id", "category", "frame_end")
    _VISUAL_KEYS = _BBOX_KEYS + ("x", "y") + _FRAME_META_KEYS

    def __init__(self, timeout_ms: int):
        """初始化协议解析器."""
        self.timeout_ms = int(timeout_ms)
        self._latest = None
        self._latest_frame = None
        self._pending_detections = []
        self._pending_camera_id = None
        self._pending_frame_id = None
        self._invalid_pending_camera_id = None
        self._invalid_pending_frame_id = None
        self._invalid_jumped_camera_id = None
        self._invalid_jumped_frame_id = None

    @staticmethod
    def _normalize_camera_id(camera_id: str) -> str:
        """归一化相机标识文本."""
        return str(camera_id).strip().lower()

    @classmethod
    def build_frame_query(cls, camera_id: str) -> str:
        """构造单相机当前帧查询串."""
        return "?frame=%s" % cls._normalize_camera_id(camera_id)

    @classmethod
    def is_query_for_camera(cls, line: str, camera_id: str) -> bool:
        """判断当前查询是否点名指定相机."""
        normalized = cls._normalize_camera_id(camera_id)
        return str(line).strip().lower() == "?frame=%s" % normalized

    @classmethod
    def is_reserved_query(cls, line: str) -> bool:
        """判断查询是否保留给视觉协议."""
        text = str(line).strip().lower()
        if not text.startswith("?frame="):
            return False
        return bool(text.split("=", 1)[1].strip())

    @staticmethod
    def _parse_line_items(line: str):
        """将单行协议文本解析为键值对列表."""
        parts = [part.strip() for part in str(line).split(",") if part.strip()]
        if not parts:
            return None

        parsed_items = []
        for part in parts:
            if "=" not in part:
                return []
            key, value_text = part.split("=", 1)
            parsed_items.append((key.strip().lower(), value_text.strip()))
        return parsed_items

    def _clear_pending_frame(self) -> None:
        """清空尚未结束的检测批次缓存."""
        self._pending_detections = []
        self._pending_camera_id = None
        self._pending_frame_id = None

    def _set_invalid_batch(
        self,
        pending_camera_id: str,
        pending_frame_id: str,
        jumped_camera_id: str,
        jumped_frame_id: str,
    ) -> None:
        """标记因批次跳变而整体失效的旧批次与跳变批次."""
        self._clear_pending_frame()
        self._invalid_pending_camera_id = str(pending_camera_id)
        self._invalid_pending_frame_id = str(pending_frame_id)
        self._invalid_jumped_camera_id = str(jumped_camera_id)
        self._invalid_jumped_frame_id = str(jumped_frame_id)

    def _clear_invalid_batch(self) -> None:
        """清空失效批次标记."""
        self._invalid_pending_camera_id = None
        self._invalid_pending_frame_id = None
        self._invalid_jumped_camera_id = None
        self._invalid_jumped_frame_id = None

    def _has_invalid_batch(self) -> bool:
        """判断当前是否处于批次失效窗口."""
        return self._invalid_pending_camera_id is not None

    def _is_invalid_batch(self, camera_id: str, frame_id: str) -> bool:
        """判断当前帧标识是否处于失效批次."""
        normalized_camera_id = str(camera_id)
        normalized_frame_id = str(frame_id)
        return (
            self._invalid_pending_camera_id == normalized_camera_id
            and self._invalid_pending_frame_id == normalized_frame_id
        ) or (
            self._invalid_jumped_camera_id == normalized_camera_id
            and self._invalid_jumped_frame_id == normalized_frame_id
        )

    def _commit_frame(self, camera_id: str, frame_id: str, detections, now_ms: int):
        """提交一帧检测集合并更新兼容观测入口."""
        frame = VisionFrame(
            camera_id=camera_id,
            frame_id=frame_id,
            detections=detections,
            timestamp_ms=now_ms,
        )
        self._latest_frame = frame
        self._latest = frame.detections[-1] if frame.detections else None
        return frame

    def _commit_pending_frame(self, now_ms: int):
        """在收到显式结束标记后提交当前批次."""
        camera_id = self._pending_camera_id
        frame_id = self._pending_frame_id
        if camera_id is None or frame_id is None:
            self._clear_pending_frame()
            return None
        frame = self._commit_frame(
            camera_id=camera_id,
            frame_id=frame_id,
            detections=self._pending_detections,
            now_ms=now_ms,
        )
        self._clear_pending_frame()
        return frame

    @classmethod
    def is_reserved_payload(cls, line: str) -> bool:
        """判断一行报文是否属于视觉协议保留载荷."""
        parsed_items = cls._parse_line_items(line)
        if parsed_items is None:
            return False

        saw_visual_key = False
        for key, _value_text in parsed_items:
            if not key:
                return saw_visual_key
            if key in cls._VISUAL_KEYS:
                saw_visual_key = True
        return saw_visual_key

    def try_parse_observation(self, line: str, source: str, now_ms: int):
        """尝试从指定来源解析一帧视觉观测.

        `UART6` 上所有包含视觉字段名的报文都保留给视觉协议处理:
        - 合法完整框 `left,top,right,bottom` 会更新最新观测
        - 旧 `x,y` 或不完整框会被吞掉,避免落入手动命令链造成歧义
        """
        if source != "uart6":
            return VisionParseResult(False, None)

        if not self.is_reserved_payload(line):
            return VisionParseResult(False, None)

        parsed_items = self._parse_line_items(line)
        if parsed_items is None:
            return VisionParseResult(False, None)
        if parsed_items == []:
            return VisionParseResult(True, None)

        keys = {}
        for key, value_text in parsed_items:
            if key in keys:
                return VisionParseResult(True, None)
            keys[key] = value_text

        if "frame_end" in keys:
            camera_id = keys.get("camera_id")
            frame_id = keys.get("frame_id")
            if camera_id is None or frame_id is None:
                self._clear_pending_frame()
                return VisionParseResult(True, None)
            if self._has_invalid_batch():
                if self._is_invalid_batch(camera_id, frame_id):
                    return VisionParseResult(True, None)
                self._clear_invalid_batch()
            if self._pending_camera_id != str(
                camera_id
            ) or self._pending_frame_id != str(frame_id):
                if self._pending_camera_id is not None:
                    self._clear_pending_frame()
                    return VisionParseResult(True, None)
                self._clear_invalid_batch()
                self._commit_frame(
                    camera_id=str(camera_id),
                    frame_id=str(frame_id),
                    detections=[],
                    now_ms=now_ms,
                )
                return VisionParseResult(True, None)
            self._commit_pending_frame(now_ms)
            return VisionParseResult(True, self._latest)

        is_multi_detection = all(
            key in keys for key in ("camera_id", "frame_id", "category")
        )
        if is_multi_detection:
            required_keys = (
                "camera_id",
                "frame_id",
                "category",
                "left",
                "top",
                "right",
                "bottom",
            )
            if tuple(sorted(keys.keys())) != tuple(sorted(required_keys)):
                return VisionParseResult(True, None)
            try:
                observation = VisionObservation(
                    left=float(keys["left"]),
                    top=float(keys["top"]),
                    right=float(keys["right"]),
                    bottom=float(keys["bottom"]),
                    timestamp_ms=now_ms,
                    camera_id=keys["camera_id"],
                    frame_id=keys["frame_id"],
                    category=keys["category"],
                )
            except ValueError:
                return VisionParseResult(True, None)
            if (
                observation.right <= observation.left
                or observation.bottom <= observation.top
            ):
                return VisionParseResult(True, None)

            camera_id = str(keys["camera_id"])
            frame_id = str(keys["frame_id"])
            if self._has_invalid_batch():
                if self._is_invalid_batch(camera_id, frame_id):
                    return VisionParseResult(True, None)
                self._clear_invalid_batch()
            if self._pending_camera_id is not None and (
                self._pending_camera_id != camera_id
                or self._pending_frame_id != frame_id
            ):
                self._set_invalid_batch(
                    pending_camera_id=self._pending_camera_id,
                    pending_frame_id=self._pending_frame_id,
                    jumped_camera_id=camera_id,
                    jumped_frame_id=frame_id,
                )
                return VisionParseResult(True, None)
            if self._pending_camera_id is None:
                self._pending_camera_id = camera_id
                self._pending_frame_id = frame_id
            self._pending_detections.append(observation)
            return VisionParseResult(True, observation)

        if len(parsed_items) != 4:
            return VisionParseResult(True, None)

        values = {}
        for key, value_text in parsed_items:
            if key not in self._BBOX_KEYS or key in values:
                return VisionParseResult(True, None)
            try:
                values[key] = float(value_text)
            except ValueError:
                return VisionParseResult(True, None)

        if values["right"] <= values["left"] or values["bottom"] <= values["top"]:
            return VisionParseResult(True, None)

        observation = VisionObservation(
            left=values["left"],
            top=values["top"],
            right=values["right"],
            bottom=values["bottom"],
            timestamp_ms=now_ms,
        )
        self._latest = observation
        self._latest_frame = None
        return VisionParseResult(True, observation)

    def get_frame(self, now_ms: int):
        """读取仍在有效期内的最新已结束检测批次."""
        if self._latest_frame is None:
            return None
        if int(now_ms) - self._latest_frame.timestamp_ms > self.timeout_ms:
            self._latest_frame = None
            if (
                self._latest is not None
                and getattr(self._latest, "frame_id", None) is not None
            ):
                self._latest = None
            return None
        return self._latest_frame

    def get_observation(self, now_ms: int):
        """读取仍在有效期内的最新视觉观测."""
        latest_frame = self.get_frame(now_ms)
        if latest_frame is None and self._latest is not None:
            if getattr(self._latest, "frame_id", None) is not None:
                return None
        if self._latest is None:
            return None

        if int(now_ms) - self._latest.timestamp_ms > self.timeout_ms:
            self._latest = None
            return None

        return self._latest

    def shift_latest_timestamp(self, delta_ms: int) -> None:
        """将最新观测时间戳整体后移,用于屏蔽调试暂停造成的超时."""
        if self._latest is None:
            if self._latest_frame is None:
                return
        if self._latest is not None:
            self._latest.timestamp_ms += int(delta_ms)
        if self._latest_frame is not None:
            self._latest_frame.timestamp_ms += int(delta_ms)

    def clear(self) -> None:
        """清空当前缓存的视觉观测."""
        self._latest = None
        self._latest_frame = None
        self._clear_pending_frame()
        self._clear_invalid_batch()
