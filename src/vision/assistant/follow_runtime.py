"""辅车角色运行时主体

@file src/vision/assistant/follow_runtime.py
"""

import math

from config import params as _params

from vision.assistant.diagnostics import build_follow_snapshot
from vision.assistant.vision_input import (
    CONSUME_ACCEPTED as VISION_CONSUME_ACCEPTED,
    CONSUME_INVALID as VISION_CONSUME_INVALID,
    AssistantVisionInput,
)


V_CMD_MAX = getattr(_params, "V_CMD_MAX")


def _default_now_ms() -> int:
    """读取毫秒时间

    @brief 同时兼容板端 ticks_ms 和主机测试环境
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def _build_input_status(snapshot: dict, last_status: str) -> str:
    """把缓存快照和最近状态收口成统一输入状态

    @brief 优先保留 error / invalid 语义, 避免被空闲快照覆盖掉
    """

    if last_status == "error":
        return "error"
    if last_status == "invalid":
        return "invalid"
    if snapshot.get("valid"):
        return "active"
    if snapshot.get("timestamp_ms") is not None:
        return "expired"
    return "idle"


def _is_velocity_fragment(fragment: str) -> bool:
    text = fragment.strip()
    if not text or "=" not in text:
        return False
    key = text.split("=", 1)[0].strip().lower()
    return key in ("vx", "vy", "omega", "w")


def _has_position_target_command(text: str) -> bool:
    for fragment in text.split(","):
        item = fragment.strip()
        if not item or "=" not in item:
            continue
        key = item.split("=", 1)[0].strip().lower()
        if key in ("x", "y", "angle", "yaw", "dx", "dy", "d_angle"):
            return True
    return False


def _canonical_velocity_key(key: str):
    key = key.strip().lower()
    if key == "vx":
        return "vx"
    if key == "vy":
        return "vy"
    if key == "omega" or key == "w":
        return "omega"
    return None


def _clamp_command_value(value: float) -> float:
    if value > V_CMD_MAX:
        return float(V_CMD_MAX)
    if value < -V_CMD_MAX:
        return float(-V_CMD_MAX)
    return float(value)


class AssistantFollowRuntime:
    """基于共享底盘装配辅车角色运行时外观

    @brief 在共享底盘外层接管 UART8 / UART6 输入与角色层诊断
    """

    def __init__(self, now_ms=None, uart6=None) -> None:
        from core.runtime import TransportCar

        # 共享底盘实例
        car = TransportCar()
        self._transport_car = car
        # 轮组状态视图
        self.wheel_states = car.wheel_states
        # IMU 视图
        self.imu = car.imu
        # 角色层毫秒时基
        self._now_ms = now_ms or _default_now_ms
        # UART6 视觉输入层
        self._vision_input = AssistantVisionInput(now_ms=self._now_ms)
        # UART6 对象引用
        self._uart6 = uart6
        # UART8 未成行文本缓冲
        self._rx_buf8 = ""
        # UART6 未成行文本缓冲
        self._rx_buf6 = ""
        # UART8 输入状态标签
        self._uart8_input_status = "idle"
        # 最近一次前馈速度量
        self._feedforward_velocity = None
        # UART6 输入状态标签
        self._vision_input_status = "idle"
        # 最近一次错误文本
        self._last_error_text = "none"
        # 位置/角度透传保护标志
        self._hold_passthrough_targets = False

    def mark_tick(self, tick=None) -> None:
        """转发 ticker 中断标记

        @brief 角色层不改时钟节拍, tick 入口仍由共享底盘处理
        """

        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        """转发 ticker 对象

        @brief 让共享底盘持有真实的控制周期驱动器
        """

        self._transport_car.set_ticker(ticker_obj)

    def step(self) -> bool:
        """执行一拍辅车角色运行时

        @brief 先跑角色层输入接管与观测记录, 再进入共享底盘的执行周期
        """

        try:
            self._run_role_cycle()
        except Exception as exc:
            self._record_error("role_cycle failed", exc)
        return self._transport_car.step()

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程

        @brief 这一拍先接管两路输入, 再把前馈和视觉修正通过共享底盘入口写回
        """

        self._process_uart8()
        self._process_uart6()
        self._write_effective_velocity()

    def build_follow_snapshot(self) -> dict:
        """返回辅车角色层最小诊断快照

        @brief 只有外部需要观察时才组织完整字典, 避免控制周期反复分配
        """

        vision_snapshot = self._vision_input.snapshot()
        vision_status = self._resolve_vision_input_status(vision_snapshot)
        return build_follow_snapshot(
            self._build_transport_command_snapshot(),
            self._uart8_input_status,
            vision_snapshot,
            vision_status,
            self._last_error_text,
        )

    def _process_uart8(self) -> None:
        # UART8 同时承载速度字段和普通命令, 角色层只接管速度量的来源状态
        uart8 = self._transport_car.uart8
        buf_len = uart8.any()
        if not buf_len:
            self._uart8_input_status = self._resolve_uart8_input_status()
            return

        try:
            self._rx_buf8 += uart8.read(buf_len).decode()
        except Exception as exc:
            self._uart8_input_status = "error"
            self._record_error("uart8 read failed", exc)
            return

        while True:
            idx = self._rx_buf8.find("\n")
            if idx == -1:
                self._uart8_input_status = self._resolve_uart8_input_status()
                return
            line = self._rx_buf8[:idx].rstrip("\r").strip()
            self._rx_buf8 = self._rx_buf8[idx + 1 :]
            consume_result, passthrough_line = self._consume_uart8_line(line)
            if consume_result == "accepted":
                self._uart8_input_status = "active"
                self._hold_passthrough_targets = False
            elif consume_result == "invalid":
                self._uart8_input_status = "invalid"
            else:
                self._uart8_input_status = self._resolve_uart8_input_status()
            if passthrough_line:
                if _has_position_target_command(passthrough_line):
                    self._hold_passthrough_targets = True
                    if consume_result != "accepted":
                        self._feedforward_velocity = None
                self._transport_car._handle_uart_line(passthrough_line, source="uart8")

    def _consume_uart8_line(self, line: str):
        text = line.strip()
        if not text or text.startswith("?"):
            return "ignored", text

        velocity_fragments = []
        passthrough_fragments = []
        for fragment in text.split(","):
            item = fragment.strip()
            if not item:
                continue
            if _is_velocity_fragment(item):
                velocity_fragments.append(item)
            else:
                passthrough_fragments.append(item)

        consume_result = "ignored"
        if velocity_fragments:
            consume_result = self._consume_velocity_fragments(
                ",".join(velocity_fragments)
            )

        passthrough_line = None
        if passthrough_fragments:
            passthrough_line = ",".join(passthrough_fragments)
        elif consume_result == "ignored":
            passthrough_line = text
        return consume_result, passthrough_line

    def _consume_velocity_fragments(self, text: str) -> str:
        parsed = {}
        for fragment in text.split(","):
            item = fragment.strip()
            if not item or "=" not in item:
                return "ignored"
            key, value_text = item.split("=", 1)
            canonical_key = _canonical_velocity_key(key)
            if canonical_key is None:
                return "ignored"
            if canonical_key in parsed:
                return "invalid"
            try:
                value = float(value_text.strip())
            except ValueError:
                return "invalid"
            if not math.isfinite(value):
                return "invalid"
            parsed[canonical_key] = _clamp_command_value(value)

        velocity = self._feedforward_velocity
        if velocity is None:
            velocity = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        else:
            velocity = dict(velocity)
        velocity.update(parsed)
        self._feedforward_velocity = velocity
        return "accepted"

    def _process_uart6(self) -> None:
        # UART6 只服务辅车角色层, 共享底盘不参与这一侧视觉输入消费
        try:
            uart6 = self._get_uart6()
        except Exception as exc:
            self._vision_input_status = "error"
            self._record_error("uart6 init failed", exc)
            return

        if uart6 is None:
            self._vision_input_status = self._resolve_vision_input_status()
            return

        buf_len = uart6.any()
        if not buf_len:
            self._vision_input_status = self._resolve_vision_input_status()
            return

        try:
            self._rx_buf6 += uart6.read(buf_len).decode()
        except UnicodeDecodeError as exc:
            self._vision_input_status = "error"
            self._record_error("uart6 decode failed", exc)
            return
        except Exception as exc:
            self._vision_input_status = "error"
            self._record_error("uart6 read failed", exc)
            return

        while True:
            idx = self._rx_buf6.find("\n")
            if idx == -1:
                self._vision_input_status = self._resolve_vision_input_status()
                return
            line = self._rx_buf6[:idx].rstrip("\r").strip()
            self._rx_buf6 = self._rx_buf6[idx + 1 :]
            consume_result = self._vision_input.consume("UART6", line)
            if consume_result == VISION_CONSUME_ACCEPTED:
                self._vision_input_status = "accepted"
            elif consume_result == VISION_CONSUME_INVALID:
                self._vision_input_status = "invalid"

    def _resolve_vision_input_status(self, snapshot=None) -> str:
        if snapshot is None:
            snapshot = self._build_vision_snapshot_fast()
        return _build_input_status(snapshot, self._vision_input_status)

    def _resolve_uart8_input_status(self) -> str:
        if self._uart8_input_status == "error":
            return "error"
        if self._uart8_input_status == "invalid":
            return "invalid"
        if self._feedforward_velocity is not None:
            return "active"
        return "idle"

    def _build_vision_snapshot_fast(self) -> dict:
        # 视觉侧同样只取有效性和时间戳, 完整快照只在对外诊断时构造
        vision = self._vision_input.get_active_observation_ref()
        if vision is not None:
            return {"valid": True, "timestamp_ms": int(vision.timestamp_ms)}
        cached = getattr(self._vision_input, "_last_observation")
        if cached is None:
            return {"valid": False, "timestamp_ms": None}
        return {"valid": False, "timestamp_ms": int(cached.timestamp_ms)}

    def _record_error(self, prefix: str, exc: Exception) -> None:
        # 只保留最近一次错误文本, 方便现场联调判断先出问题的输入来源
        self._last_error_text = "%s: %s" % (prefix, exc)
        self._transport_car.last_exception_text = self._last_error_text

    def _write_effective_velocity(self) -> None:
        if self._should_skip_velocity_write():
            return
        velocity = self._feedforward_velocity
        if velocity is None:
            return

        vx = float(velocity.get("vx", 0.0))
        vy = float(velocity.get("vy", 0.0))
        omega = float(velocity.get("omega", 0.0))
        vision = self._vision_input.get_active_observation_ref()
        if vision is not None:
            vx += float(vision.x)
            vy += float(vision.y)
        self._transport_car._handle_uart_line(
            self._format_velocity_command(vx, vy, omega), source="uart8"
        )

    def _should_skip_velocity_write(self) -> bool:
        if not self._hold_passthrough_targets:
            return False

        last_cmd = self._transport_car.last_cmd
        active = (
            last_cmd.get("x") is not None
            or last_cmd.get("y") is not None
            or last_cmd.get("angle") is not None
        )
        if not active:
            self._hold_passthrough_targets = False
            return False
        return True

    @staticmethod
    def _format_velocity_command(vx: float, vy: float, omega: float) -> str:
        return "vx=%s,vy=%s,omega=%s" % (vx, vy, omega)

    def _build_transport_command_snapshot(self) -> dict:
        # 角色层只导出共享底盘当前真实生效的命令状态, 不再额外维护 UART8 速度缓存
        return dict(self._transport_car.last_cmd)

    def _get_uart6(self):
        # 需要读取视觉时再创建 UART6, 避免角色对象构造期碰硬件
        uart6 = self._uart6
        if uart6 is not None:
            return uart6

        from hardware.uart_bus import create_uart6

        uart6 = create_uart6()
        self._uart6 = uart6
        return uart6


def create_transport_car() -> AssistantFollowRuntime:
    """创建辅车角色运行时对象

    @brief 给角色分发入口返回会进入控制周期的辅车运行时
    """

    return AssistantFollowRuntime()
