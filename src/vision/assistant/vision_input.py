"""辅车 UART6 本地视觉输入层

@file src/vision/assistant/vision_input.py
"""

import math


# 不属于视觉输入层的输入状态
CONSUME_IGNORED = "ignored"
# 有效视觉输入状态
CONSUME_ACCEPTED = "accepted"
# 命中视觉协议但内容非法的输入状态
CONSUME_INVALID = "invalid"


def _default_now_ms() -> int:
    """读取毫秒时间

    @brief 兼容板端 ticks_ms 和主机测试环境
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


class VisionObservation:
    """最近一次有效的视觉观测快照

    @brief 保存角色层可用的本地视觉纠偏输入
    """

    __slots__ = ("x", "y", "timestamp_ms")

    def __init__(self, x: float, y: float, timestamp_ms: int) -> None:
        self.x = x
        self.y = y
        self.timestamp_ms = timestamp_ms


class AssistantVisionInput:
    """识别并缓存 UART6 上的 x/y 视觉观测

    @brief 严格按 x=<x>,y=<y> 协议接收本地视觉输入
    """

    __slots__ = ("_validity_ms", "_now_ms", "_last_observation")

    def __init__(self, validity_ms: int = 150, now_ms=None) -> None:
        # 视觉观测有效期, 单位 ms
        self._validity_ms = int(validity_ms)
        # 毫秒时间函数
        self._now_ms = now_ms or _default_now_ms
        # 最近一次视觉观测缓存
        self._last_observation = None

    def consume(self, source: str, line: str) -> str:
        """尝试消费一行视觉协议

        @brief 只接受 UART6 上的 x=<x>,y=<y>, 避免把其他串口文本误识别成视觉输入
        """

        if source.strip().upper() != "UART6":
            return CONSUME_IGNORED

        text = line.strip()
        if not text or text.startswith("?") or "=" not in text:
            return CONSUME_IGNORED

        # 协议固定为两字段定序输入, 这里故意不放宽顺序和字段数量
        parts = text.split(",")
        if len(parts) == 1:
            return CONSUME_IGNORED
        if len(parts) != 2:
            return CONSUME_INVALID

        x_text, y_text = parts
        if not x_text.startswith("x=") or not y_text.startswith("y="):
            return CONSUME_INVALID

        try:
            x_value = float(x_text[2:])
            y_value = float(y_text[2:])
        except ValueError:
            return CONSUME_INVALID

        if not math.isfinite(x_value) or not math.isfinite(y_value):
            return CONSUME_INVALID

        self._last_observation = VisionObservation(
            x=x_value,
            y=y_value,
            timestamp_ms=self._read_now_ms(),
        )
        return CONSUME_ACCEPTED

    def get_active_observation(self):
        """返回仍在有效期内的观测副本

        @brief 对外查询时返回副本, 避免外部改坏内部缓存
        """

        observation = self.get_active_observation_ref()
        if observation is None:
            return None
        return VisionObservation(
            x=observation.x,
            y=observation.y,
            timestamp_ms=observation.timestamp_ms,
        )

    def get_active_observation_ref(self):
        """返回内部缓存的有效观测引用

        @brief 只给角色层热路径只读使用, 减少控制周期里的复制开销
        """

        observation = self._last_observation
        if observation is None:
            return None
        if self._read_now_ms() - observation.timestamp_ms > self._validity_ms:
            return None
        return observation

    def get_observation_age_ms(self):
        """返回有效观测年龄

        @brief 诊断时用年龄区分观测是否已过期
        """

        observation = self.get_active_observation()
        if observation is None:
            return None
        return max(0, self._read_now_ms() - observation.timestamp_ms)

    def snapshot(self) -> dict:
        """返回视觉缓存的只读快照

        @brief 诊断层导出完整字段, 热路径不直接依赖这里
        """

        observation = self._last_observation
        if observation is None:
            return {
                "valid": False,
                "x": None,
                "y": None,
                "timestamp_ms": None,
                "age_ms": None,
            }

        return {
            "valid": self.get_active_observation() is not None,
            "x": observation.x,
            "y": observation.y,
            "timestamp_ms": observation.timestamp_ms,
            "age_ms": self.get_observation_age_ms(),
        }

    def _read_now_ms(self) -> int:
        return int(self._now_ms())
