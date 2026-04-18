"""辅车视觉向量缓存层

@file src/vision/assistant/vision_input.py
"""

from vision.assistant.velocity_packet import (
    CONSUME_ACCEPTED,
    CONSUME_IGNORED,
    CONSUME_INVALID,
    split_velocity_line,
)


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

    @brief 保存角色层可观察的本地视觉输入
    """

    __slots__ = ("x", "y", "omega", "timestamp_ms")

    def __init__(self, x: float, y: float, omega: float, timestamp_ms: int) -> None:
        self.x = x
        self.y = y
        self.omega = omega
        self.timestamp_ms = timestamp_ms


class AssistantVisionInput:
    """识别并缓存指定来源上的视觉向量

    @brief 以共享速度字段语义接收指定来源输入，并缓存成角色层观测
    """

    __slots__ = ("_now_ms", "_last_observation", "_source_name")

    def __init__(self, now_ms=None, source_name: str = "UART8") -> None:
        # 毫秒时间函数
        self._now_ms = now_ms or _default_now_ms
        # 最近一次视觉观测缓存
        self._last_observation = None
        # 当前视觉向量来源标签
        self._source_name = str(source_name).strip().upper()

    def consume(self, source: str, line: str) -> str:
        """尝试消费一行视觉协议

        @brief 只消费配置来源上的速度字段，供独立文本入口把当前包解释为视觉贡献向量
        """

        if source.strip().upper() != self._source_name:
            return CONSUME_IGNORED

        consume_result, parsed, _passthrough_line = split_velocity_line(line)
        if consume_result != CONSUME_ACCEPTED or parsed is None:
            return consume_result

        self.record_velocity_vector(parsed)
        return CONSUME_ACCEPTED

    def record_velocity_vector(self, parsed: dict) -> None:
        """缓存一份已解析好的速度向量。

        @brief 供角色运行时在共享解析边界之后直接写入视觉向量缓存
        """

        observation = self._last_observation
        timestamp_ms = self._read_now_ms()
        if observation is None:
            self._last_observation = VisionObservation(
                x=float(parsed.get("vx", 0.0)),
                y=float(parsed.get("vy", 0.0)),
                omega=float(parsed.get("omega", 0.0)),
                timestamp_ms=timestamp_ms,
            )
            return

        observation.x = float(parsed.get("vx", 0.0))
        observation.y = float(parsed.get("vy", 0.0))
        observation.omega = float(parsed.get("omega", 0.0))
        observation.timestamp_ms = timestamp_ms

    def has_observation(self) -> bool:
        """返回是否已有视觉向量缓存。"""

        return self._last_observation is not None

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
            omega=observation.omega,
            timestamp_ms=observation.timestamp_ms,
        )

    def get_active_observation_ref(self):
        """返回内部缓存的有效观测引用

        @brief 只给角色层热路径只读使用, 减少控制周期里的复制开销
        """

        observation = self._last_observation
        return observation

    def get_observation_age_ms(self):
        """返回有效观测年龄

        @brief 诊断时用年龄区分观测是否已过期
        """

        observation = self.get_active_observation()
        if observation is None:
            return None
        return max(0, self._read_now_ms() - observation.timestamp_ms)

    def clear(self) -> None:
        """清空当前缓存观测。"""

        self._last_observation = None

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
                "omega": None,
                "timestamp_ms": None,
                "age_ms": None,
            }

        return {
            "valid": self.get_active_observation() is not None,
            "x": observation.x,
            "y": observation.y,
            "omega": observation.omega,
            "timestamp_ms": observation.timestamp_ms,
            "age_ms": self.get_observation_age_ms(),
        }

    def _read_now_ms(self) -> int:
        return int(self._now_ms())
