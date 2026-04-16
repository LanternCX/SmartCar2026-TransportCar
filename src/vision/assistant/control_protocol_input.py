"""辅车 UART3 速度控制协议输入层

@file src/vision/assistant/control_protocol_input.py
"""

import math

from config import params as _params


# 速度字段使用共享控制协议的同一组幅值边界
V_CMD_MAX = getattr(_params, "V_CMD_MAX")
# 这一行不属于速度控制输入层的消费范围
CONSUME_IGNORED = "ignored"
# 这一行被识别为有效速度控制量并刷新缓存
CONSUME_ACCEPTED = "accepted"
# 这一行命中了速度字段, 但内容非法
CONSUME_INVALID = "invalid"


def _default_now_ms() -> int:
    """读取毫秒时间

    @brief 兼容主机测试和板端的时间来源
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


class VelocityControl:
    """最近一次有效的速度控制量快照

    @brief 供角色层在控制周期内直接读取速度节奏
    """

    __slots__ = ("vx", "vy", "omega", "timestamp_ms")

    def __init__(
        self,
        vx: float,
        vy: float,
        omega: float,
        timestamp_ms: int,
    ) -> None:
        self.vx = vx
        self.vy = vy
        self.omega = omega
        self.timestamp_ms = timestamp_ms


class ControlProtocolInput:
    """识别并缓存 UART3 上的速度控制包

    @brief 只接管现有控制协议中的速度字段, 不处理其他命令
    """

    __slots__ = ("_validity_ms", "_now_ms", "_last_control")

    def __init__(self, validity_ms: int = 150, now_ms=None) -> None:
        # 控制量超时后直接失效, 避免角色层长期保留过期节奏
        self._validity_ms = int(validity_ms)
        # 时间函数允许测试注入, 避免协议层依赖真实时钟
        self._now_ms = now_ms or _default_now_ms
        # 只保留最近一次速度控制量, 让角色层按最新节奏运行
        self._last_control = None

    def consume(self, line: str) -> str:
        """尝试消费一行控制协议

        @brief 只解析 vx / vy / omega / w, 其他字段留给外层决定是否透传
        """

        text = line.strip()
        if not text or text.startswith("?") or "=" not in text:
            return CONSUME_IGNORED

        # 现有协议允许单字段和多字段同包, 这里统一按逗号拆开处理
        parts = text.split(",")
        parsed = {}

        for part in parts:
            item = part.strip()
            if not item or "=" not in item:
                return CONSUME_IGNORED

            key, value_text = item.split("=", 1)
            key = key.strip().lower()
            value_text = value_text.strip()
            canonical_key = self._canonical_key(key)
            if canonical_key is None:
                return CONSUME_IGNORED

            if canonical_key in parsed:
                return CONSUME_INVALID

            try:
                value = float(value_text)
            except ValueError:
                return CONSUME_INVALID

            if not math.isfinite(value):
                return CONSUME_INVALID
            if value < -V_CMD_MAX or value > V_CMD_MAX:
                return CONSUME_INVALID

            parsed[canonical_key] = value

        self._last_control = self._merge_control(parsed)
        return CONSUME_ACCEPTED

    def get_active_control(self):
        """返回仍在有效期内的控制量

        @brief 热路径直接读取内部缓存, 超时后立即失效
        """

        control = self._last_control
        if control is None:
            return None
        if self._read_now_ms() - control.timestamp_ms > self._validity_ms:
            return None
        return control

    def snapshot(self) -> dict:
        """返回缓存的只读诊断快照

        @brief 诊断时导出完整字段, 不把内部对象直接暴露给外层
        """

        control = self._last_control
        active = self.get_active_control()
        if control is None:
            return {
                "valid": False,
                "vx": None,
                "vy": None,
                "omega": None,
                "timestamp_ms": None,
                "age_ms": None,
            }
        return {
            "valid": active is not None,
            "vx": control.vx,
            "vy": control.vy,
            "omega": control.omega,
            "timestamp_ms": control.timestamp_ms,
            "age_ms": max(0, self._read_now_ms() - control.timestamp_ms),
        }

    def _read_now_ms(self) -> int:
        return int(self._now_ms())

    def _merge_control(self, parsed: dict) -> VelocityControl:
        # 单字段更新需要保留同一控制包里未出现的另外两轴
        control = self._last_control
        if control is None:
            vx = 0.0
            vy = 0.0
            omega = 0.0
        else:
            vx = control.vx
            vy = control.vy
            omega = control.omega

        if "vx" in parsed:
            vx = parsed["vx"]
        if "vy" in parsed:
            vy = parsed["vy"]
        if "omega" in parsed:
            omega = parsed["omega"]

        return VelocityControl(
            vx=vx,
            vy=vy,
            omega=omega,
            timestamp_ms=self._read_now_ms(),
        )

    @staticmethod
    def _canonical_key(key: str):
        # w 在角色层统一折叠为 omega, 这样融合层只处理一种角速度字段
        if key == "vx":
            return "vx"
        if key == "vy":
            return "vy"
        if key == "omega" or key == "w":
            return "omega"
        return None
