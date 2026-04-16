"""辅车角色运行时主体

@file src/vision/assistant/follow_runtime.py
"""

from config import params as _params

from vision.assistant.control_protocol_input import (
    CONSUME_ACCEPTED as CONTROL_CONSUME_ACCEPTED,
    CONSUME_IGNORED as CONTROL_CONSUME_IGNORED,
    CONSUME_INVALID as CONTROL_CONSUME_INVALID,
    ControlProtocolInput,
)
from vision.assistant.diagnostics import build_follow_snapshot
from vision.assistant.velocity_fusion import FusionResult, VelocityFusion
from vision.assistant.vision_input import (
    CONSUME_ACCEPTED as VISION_CONSUME_ACCEPTED,
    CONSUME_INVALID as VISION_CONSUME_INVALID,
    AssistantVisionInput,
)


# 融合输出速度上限
TARGET_SPEED_MAX = getattr(_params, "TARGET_SPEED_MAX")


def _default_now_ms() -> int:
    """读取毫秒时间

    @brief 同时兼容板端 ticks_ms 和主机测试环境
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def _is_velocity_fragment(fragment: str) -> bool:
    """判断 UART8 文本片段是否属于速度字段

    @brief 只接管 vx / vy / omega / w, 其余字段交给共享底盘处理
    """

    text = fragment.strip()
    if not text or "=" not in text:
        return False
    key = text.split("=", 1)[0].strip().lower()
    return key in ("vx", "vy", "omega", "w")


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


def _has_position_target_command(text: str) -> bool:
    """判断透传命令里是否含有位置或角度目标

    @brief 这些目标需要短暂压住角色层速度写回, 避免同拍被立即冲掉
    """

    for fragment in text.split(","):
        item = fragment.strip()
        if not item or "=" not in item:
            continue
        key = item.split("=", 1)[0].strip().lower()
        if key in ("x", "y", "angle", "yaw", "dx", "dy", "d_angle"):
            return True
    return False


class AssistantFollowRuntime:
    """基于共享底盘装配辅车角色运行时外观

    @brief 在共享底盘外层接管串口输入、速度融合和角色层诊断
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
        # UART8 速度控制输入层
        self._control_input = ControlProtocolInput(now_ms=self._now_ms)
        # UART6 视觉输入层
        self._vision_input = AssistantVisionInput(now_ms=self._now_ms)
        # 速度融合器
        self._fusion = VelocityFusion(
            output_limit=TARGET_SPEED_MAX,
            degraded_output_limit=TARGET_SPEED_MAX / 3.0,
        )
        # UART6 对象引用
        self._uart6 = uart6
        # UART8 未成行文本缓冲
        self._rx_buf8 = ""
        # UART6 未成行文本缓冲
        self._rx_buf6 = ""
        # UART8 输入状态标签
        self._control_input_status = "idle"
        # UART6 输入状态标签
        self._vision_input_status = "idle"
        # 最近一次错误文本
        self._last_error_text = "none"
        # 位置/角度透传保护标志
        self._hold_passthrough_targets = False
        # 最近一次融合结果引用
        self._last_fusion = None

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

        @brief 先跑角色层输入接管和融合, 再进入共享底盘的执行周期
        """

        try:
            self._run_role_cycle()
        except Exception as exc:
            self._record_error("role_cycle failed", exc)
            fusion = self._fusion.fuse(control=None, vision=None)
            self._write_fused_velocity(fusion)
            self._refresh_runtime_state(fusion)
        return self._transport_car.step()

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程

        @brief 这一拍先接管两路输入, 再生成统一速度目标并刷新最小状态
        """

        self._process_uart8()
        self._process_uart6()
        control = self._control_input.get_active_control()
        vision = self._vision_input.get_active_observation_ref()
        fusion = self._fusion.fuse(control=control, vision=vision)
        if not self._should_skip_velocity_write():
            self._write_fused_velocity(fusion)
        self._refresh_runtime_state(fusion)

    def build_follow_snapshot(self) -> dict:
        """返回辅车角色层最小诊断快照

        @brief 只有外部需要观察时才组织完整字典, 避免控制周期反复分配
        """

        control_snapshot = self._control_input.snapshot()
        vision_snapshot = self._vision_input.snapshot()
        control_status = self._resolve_control_input_status(control_snapshot)
        vision_status = self._resolve_vision_input_status(vision_snapshot)
        return build_follow_snapshot(
            control_snapshot,
            control_status,
            vision_snapshot,
            vision_status,
            self._last_error_text,
            self._last_fusion,
        )

    def _process_uart8(self) -> None:
        # UART8 同时承载速度字段和普通控制命令, 这里先拆分再决定接管或透传
        uart8 = self._transport_car.uart8
        buf_len = uart8.any()
        if not buf_len:
            self._control_input_status = self._resolve_control_input_status()
            return

        try:
            self._rx_buf8 += uart8.read(buf_len).decode()
        except Exception as exc:
            self._control_input_status = "error"
            self._record_error("uart8 read failed", exc)
            return

        while True:
            idx = self._rx_buf8.find("\n")
            if idx == -1:
                self._control_input_status = self._resolve_control_input_status()
                return
            line = self._rx_buf8[:idx].rstrip("\r").strip()
            self._rx_buf8 = self._rx_buf8[idx + 1 :]
            consume_result, passthrough_line = self._consume_uart8_line(line)
            if consume_result == CONTROL_CONSUME_ACCEPTED:
                self._control_input_status = "accepted"
                self._hold_passthrough_targets = False
            elif consume_result == CONTROL_CONSUME_INVALID:
                self._control_input_status = "invalid"
            elif consume_result == CONTROL_CONSUME_IGNORED:
                self._control_input_status = self._resolve_control_input_status()
            if passthrough_line:
                if _has_position_target_command(passthrough_line):
                    # 位置目标透传后先保住共享底盘上的目标状态, 等下一拍再判断是否让位
                    self._hold_passthrough_targets = True
                self._transport_car._handle_uart_line(passthrough_line, source="uart8")

    def _consume_uart8_line(self, line: str):
        # 混合包先拆出速度字段, 这样速度接管和普通命令透传就不会互相踩掉
        text = line.strip()
        if not text or text.startswith("?"):
            return CONTROL_CONSUME_IGNORED, text

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

        consume_result = CONTROL_CONSUME_IGNORED
        if velocity_fragments:
            consume_result = self._control_input.consume(",".join(velocity_fragments))

        passthrough_line = None
        if passthrough_fragments:
            passthrough_line = ",".join(passthrough_fragments)
        elif consume_result == CONTROL_CONSUME_IGNORED:
            passthrough_line = text
        return consume_result, passthrough_line

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

    def _write_fused_velocity(self, fusion: FusionResult) -> None:
        # 速度重新接管时只清理位置/角度目标, 不重走共享底盘整包收口, 避免顺手改坏共存状态
        last_cmd = self._transport_car.last_cmd
        if (
            last_cmd.get("x") is not None
            or last_cmd.get("y") is not None
            or last_cmd.get("angle") is not None
        ):
            last_cmd.pop("x", None)
            last_cmd.pop("y", None)
            last_cmd.pop("angle", None)
        last_cmd["vx"] = float(fusion.vx)
        last_cmd["vy"] = float(fusion.vy)
        last_cmd["omega"] = float(fusion.omega)

    def _should_skip_velocity_write(self) -> bool:
        # 只在共享底盘仍挂着位置/角度目标时暂停速度写回
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

    def _refresh_runtime_state(self, fusion: object) -> None:
        # 控制周期里只缓存轻量状态, 完整诊断字典留到查询时再构造
        self._last_fusion = fusion
        self._control_input_status = self._resolve_control_input_status()
        self._vision_input_status = self._resolve_vision_input_status()

    def _resolve_control_input_status(self, snapshot=None) -> str:
        if snapshot is None:
            snapshot = self._build_control_snapshot_fast()
        return _build_input_status(snapshot, self._control_input_status)

    def _resolve_vision_input_status(self, snapshot=None) -> str:
        if snapshot is None:
            snapshot = self._build_vision_snapshot_fast()
        return _build_input_status(snapshot, self._vision_input_status)

    def _build_control_snapshot_fast(self) -> dict:
        # 热路径只保留状态判断必需字段, 避免每拍复制完整控制量字典
        control = self._control_input.get_active_control()
        if control is not None:
            return {"valid": True, "timestamp_ms": int(control.timestamp_ms)}
        cached = getattr(self._control_input, "_last_control")
        if cached is None:
            return {"valid": False, "timestamp_ms": None}
        return {"valid": False, "timestamp_ms": int(cached.timestamp_ms)}

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
