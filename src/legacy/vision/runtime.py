"""视觉运行时 owner 与固定槽位结构."""


class VisionCameraSlot:
    """保存单个相机槽位的最小运行时状态."""

    __slots__ = (
        "camera_id",
        "frame",
        "pending_frame_id",
        "pending_items",
        "timestamp_ms",
    )

    def __init__(self, camera_id: str):
        """按固定相机 ID 初始化空槽位."""
        self.camera_id = str(camera_id)
        self.frame = None
        self.pending_frame_id = None
        self.pending_items = None
        self.timestamp_ms = None


class VisionRuntime:
    """保存视觉链路单一 owner 所需的基础槽位."""

    __slots__ = (
        "timeout_ms",
        "cam_a",
        "cam_b",
        "latest_frame",
        "latest_observation",
        "selected_input",
        "resolved_target",
        "snapshot_buffer",
    )

    def __init__(self, timeout_ms: int):
        """初始化双摄固定槽位和基础运行时引用."""
        self.timeout_ms = int(timeout_ms)
        self.cam_a = VisionCameraSlot("cam_a")
        self.cam_b = VisionCameraSlot("cam_b")
        self.latest_frame = None
        self.latest_observation = None
        self.selected_input = None
        self.resolved_target = None
        self.snapshot_buffer = None

    def get_slot(self, camera_id: str):
        """按相机 ID 返回固定槽位, 未知相机回退主槽位."""
        normalized = str(camera_id).strip().lower()
        if normalized == "cam_b":
            return self.cam_b
        return self.cam_a
