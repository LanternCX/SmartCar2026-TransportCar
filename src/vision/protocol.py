"""视觉协议解析与最新观测缓存."""


class VisionObservation:
    """单帧视觉识别框观测."""

    def __init__(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        timestamp_ms: int,
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
    _VISUAL_KEYS = _BBOX_KEYS + ("x", "y")

    def __init__(self, timeout_ms: int):
        """初始化协议解析器."""
        self.timeout_ms = int(timeout_ms)
        self._latest = None

    def try_parse_observation(self, line: str, source: str, now_ms: int):
        """尝试从指定来源解析一帧视觉观测.

        `UART6` 上所有包含视觉字段名的报文都保留给视觉协议处理:
        - 合法完整框 `left,top,right,bottom` 会更新最新观测
        - 旧 `x,y` 或不完整框会被吞掉,避免落入手动命令链造成歧义
        """
        if source != "uart6":
            return VisionParseResult(False, None)

        parts = [part.strip() for part in line.split(",") if part.strip()]
        if not parts:
            return VisionParseResult(False, None)

        parsed_items = []
        saw_visual_key = False
        for part in parts:
            if "=" not in part:
                return VisionParseResult(saw_visual_key, None)
            key, value_text = part.split("=", 1)
            key = key.strip().lower()
            if key in self._VISUAL_KEYS:
                saw_visual_key = True
            parsed_items.append((key, value_text.strip()))

        if not saw_visual_key:
            return VisionParseResult(False, None)

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
        return VisionParseResult(True, observation)

    def get_observation(self, now_ms: int):
        """读取仍在有效期内的最新视觉观测."""
        if self._latest is None:
            return None

        if int(now_ms) - self._latest.timestamp_ms > self.timeout_ms:
            self._latest = None
            return None

        return self._latest

    def shift_latest_timestamp(self, delta_ms: int) -> None:
        """将最新观测时间戳整体后移,用于屏蔽调试暂停造成的超时."""
        if self._latest is None:
            return
        self._latest.timestamp_ms += int(delta_ms)

    def clear(self) -> None:
        """清空当前缓存的视觉观测."""
        self._latest = None
