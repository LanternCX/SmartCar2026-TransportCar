"""视觉协议解析与最新观测缓存."""


class VisionObservation:
    """单帧视觉目标点观测."""

    def __init__(self, x: float, y: float, timestamp_ms: int):
        """保存视觉观测值与时间戳."""
        self.x = float(x)
        self.y = float(y)
        self.timestamp_ms = int(timestamp_ms)


class VisionProtocol:
    """解析 UART6 纯 x,y 视觉包并维护最新观测."""

    def __init__(self, timeout_ms: int):
        """初始化协议解析器."""
        self.timeout_ms = int(timeout_ms)
        self._latest = None

    def try_parse_observation(self, line: str, source: str, now_ms: int):
        """尝试从指定来源解析一帧视觉观测."""
        if source != "uart6":
            return None

        parts = [part.strip() for part in line.split(",") if part.strip()]
        if len(parts) != 2:
            return None

        values = {}
        for part in parts:
            if "=" not in part:
                return None
            key, value_text = part.split("=", 1)
            key = key.strip().lower()
            if key not in ("x", "y") or key in values:
                return None
            try:
                values[key] = float(value_text.strip())
            except ValueError:
                return None

        if "x" not in values or "y" not in values:
            return None

        observation = VisionObservation(
            x=values["x"], y=values["y"], timestamp_ms=now_ms
        )
        self._latest = observation
        return observation

    def get_observation(self, now_ms: int):
        """读取仍在有效期内的最新视觉观测."""
        if self._latest is None:
            return None

        if int(now_ms) - self._latest.timestamp_ms > self.timeout_ms:
            self._latest = None
            return None

        return self._latest

    def clear(self) -> None:
        """清空当前缓存的视觉观测."""
        self._latest = None
